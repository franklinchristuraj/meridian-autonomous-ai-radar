# Phase 5: LLM Observability - Research

**Researched:** 2026-03-16
**Domain:** OpenTelemetry + Arize Phoenix instrumentation for Python pipelines
**Confidence:** HIGH

## Summary

Phase 5 instruments the Meridian daily pipeline (Scout → Analyst → Briefing → Translator) to send OpenTelemetry traces to the existing self-hosted Phoenix Docker instance. The approach uses `arize-phoenix-otel` for Phoenix-aware OTEL configuration, `openinference-semantic-conventions` for standard LLM span attributes, and manual span creation via the standard `opentelemetry-api` — no auto-instrumentation framework (LangChain, OpenAI SDK) applies here since Meridian calls Claude via subprocess.

The key architectural decision is a single root span per daily pipeline run, with four child spans (one per stage), and a dedicated `invoke_claude()` wrapper that adds LLM-specific attributes (token counts, cost, model, prompt/response payloads) to each LLM child span. A `TracerProvider` is initialized once at application startup via `register()` and the tracer is passed through pipeline stages via a shared tracer module.

**Primary recommendation:** Use `arize-phoenix-otel` + `openinference-semantic-conventions` + `opentelemetry-api/sdk`. Initialize with `register(endpoint="http://<phoenix-host>:6006/v1/traces")` at FastAPI startup. Instrument manually — no auto-instrumentation framework applies.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Instrument the full pipeline end-to-end, not just LLM calls
- Covers: ArXiv fetch, Weaviate queries, LLM calls (invoke_claude), file writes, heartbeat writes
- Each daily pipeline run = one trace with child spans per stage (Scout, Analyst, Briefing, Translator)
- Existing heartbeat JSON files kept alongside Phoenix — no breaking changes
- Span metadata: token counts (input/output), cost_usd, model identity, full input/output payloads, item counts per stage
- Phoenix UI only — no custom dashboard in the Meridian PWA
- Phoenix already running as separate Docker container on VPS
- Primary metric: signal quality funnel (papers → signals → clusters → seeds)

### Claude's Discretion
- OpenTelemetry SDK configuration details
- Span naming conventions
- Phoenix collector endpoint configuration
- How to structure trace context passing between pipeline stages
- Data retention / trace cleanup policy

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| arize-phoenix-otel | 0.15.0 | Phoenix-aware OTEL setup, `register()` helper | Official Phoenix client; handles endpoint config, batch export, env var defaults |
| opentelemetry-api | >=1.20 | Tracer, Span, context propagation APIs | Standard OTel; `arize-phoenix-otel` depends on it |
| opentelemetry-sdk | >=1.20 | TracerProvider, BatchSpanProcessor, in-memory export | Standard OTel SDK for local export |
| opentelemetry-exporter-otlp-proto-http | >=1.20 | HTTP/protobuf export to Phoenix `/v1/traces` | Phoenix self-hosted uses HTTP endpoint on port 6006 |
| openinference-semantic-conventions | >=0.1 | Standard LLM attribute names (token counts, cost, model, payload) | OpenInference spec — Phoenix understands these natively |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| opentelemetry-exporter-otlp-proto-grpc | >=1.20 | gRPC export alternative | Only if HTTP export causes issues; default Phoenix port 4317 |

**Installation:**
```bash
pip install arize-phoenix-otel openinference-semantic-conventions opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
```

Add to `requirements.txt`:
```
arize-phoenix-otel>=0.15,<1
openinference-semantic-conventions>=0.1,<1
opentelemetry-api>=1.20,<2
opentelemetry-sdk>=1.20,<2
opentelemetry-exporter-otlp-proto-http>=1.20,<2
```

---

## Architecture Patterns

### Recommended Project Structure
```
src/
├── runtime/
│   ├── claude_runner.py     # existing — add span instrumentation here
│   └── tracer.py            # NEW — single module to initialize + expose tracer
├── pipeline/
│   ├── scout.py             # wrap stage body in with tracer.start_as_current_span()
│   ├── analyst.py           # same
│   ├── briefing.py          # same
│   └── translator.py        # same
└── api/
    └── lifespan.py (or main.py)  # call register() at startup
```

### Pattern 1: Centralized Tracer Module
**What:** Single `src/runtime/tracer.py` creates and exposes a module-level tracer. All pipeline modules import from it.
**When to use:** Always — avoids passing tracer as function argument through the call chain.

```python
# src/runtime/tracer.py
# Source: https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel
from phoenix.otel import register

def init_tracing(endpoint: str, project_name: str = "meridian") -> None:
    register(
        endpoint=endpoint,          # e.g. "http://<vps-ip>:6006/v1/traces"
        project_name=project_name,
        batch=True,                 # BatchSpanProcessor — non-blocking
    )

# After init_tracing() is called, use the standard OTel API:
from opentelemetry import trace
tracer = trace.get_tracer("meridian.pipeline")
```

Call `init_tracing()` once at FastAPI app startup (lifespan event or `main.py`). The global TracerProvider is set; all subsequent `trace.get_tracer()` calls return live tracers.

### Pattern 2: Root + Stage Spans
**What:** One root span per pipeline run wraps all four stages as child spans. Context propagates automatically via OTel's implicit context.

```python
# Pipeline entry point (scheduler or webhook handler)
# Source: opentelemetry-api docs — context propagation via with-block
with tracer.start_as_current_span("meridian.pipeline.run") as root_span:
    root_span.set_attribute("pipeline.trigger", "scheduler")  # or "webhook"
    root_span.set_attribute("pipeline.date", date_str)
    run_scout()       # scout creates child span internally
    run_analyst()     # etc.
    run_briefing()
    run_translator()
```

### Pattern 3: LLM Span Attributes via OpenInference Conventions
**What:** Use OpenInference semantic convention attribute keys on every `invoke_claude()` span.

```python
# src/runtime/claude_runner.py — instrumented version
# Source: https://arize-ai.github.io/openinference/spec/semantic_conventions.html
from openinference.semconv.trace import SpanAttributes
from opentelemetry import trace

tracer = trace.get_tracer("meridian.llm")

def invoke_claude(prompt: str, model: str = "claude-sonnet-4-5", timeout: int = 120) -> dict:
    with tracer.start_as_current_span("invoke_claude") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "LLM")
        span.set_attribute(SpanAttributes.LLM_MODEL_NAME, model)
        span.set_attribute(SpanAttributes.INPUT_VALUE, prompt)

        result = _run_subprocess(prompt, model, timeout)  # existing logic

        usage = result.get("usage", {})
        span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_PROMPT, usage.get("input_tokens", 0))
        span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_COMPLETION, usage.get("output_tokens", 0))
        span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_TOTAL,
                           usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
        span.set_attribute("llm.cost_usd", result.get("cost_usd", 0.0))
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, result.get("result", ""))
        return result
```

### Pattern 4: Business Metric Spans (Stage-Level)
**What:** Each pipeline stage span records domain counts — papers fetched, signals scored, clusters, seeds.

```python
# src/pipeline/scout.py — example
with tracer.start_as_current_span("meridian.stage.scout") as span:
    papers = fetch_arxiv(...)
    span.set_attribute("scout.papers_fetched", len(papers))
    signals = score_signals(papers)
    span.set_attribute("scout.signals_scored", len(signals))
```

### Anti-Patterns to Avoid
- **Passing tracer as function argument:** Creates coupling across the entire call chain. Use module-level `trace.get_tracer()` instead — OTel context propagates implicitly via thread-local context.
- **Initializing TracerProvider in each pipeline module:** Results in multiple providers and broken traces. Initialize once at startup only.
- **Using `start_span()` without a `with` block:** Span won't be closed on exception. Always use `start_as_current_span()` as a context manager.
- **Storing full payloads as span events instead of attributes:** Phoenix's drill-down UI expects `INPUT_VALUE`/`OUTPUT_VALUE` attributes on the span, not events.
- **Blocking span export on shutdown:** Use `BatchSpanProcessor` (default with `register(batch=True)`) — not `SimpleSpanProcessor` which blocks the event loop.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Trace/span context propagation | Custom thread-local context passing | OTel implicit context (`start_as_current_span` with-block) | Parent-child linking is automatic; manual wiring breaks on exceptions |
| LLM attribute naming | Custom attribute key strings | `openinference.semconv.trace.SpanAttributes` constants | Phoenix parses these known keys for its built-in views (token cost, latency) |
| Phoenix OTLP endpoint config | Custom HTTP export logic | `register()` from `arize-phoenix-otel` | Handles batching, retry, env var fallback, protocol negotiation |
| Span error recording | Manual error string attributes | `span.record_exception(e)` + `span.set_status(StatusCode.ERROR, str(e))` | Standard OTel exception recording; Phoenix surfaces these in error views |

---

## Common Pitfalls

### Pitfall 1: OTLP Endpoint Port Confusion
**What goes wrong:** Traces silently dropped because the wrong port is used.
**Why it happens:** Phoenix exposes two endpoints — HTTP on port 6006 (`/v1/traces`) and gRPC on port 4317. `register()` defaults to gRPC (4317) if only a hostname is given.
**How to avoid:** Always pass the full HTTP URL: `register(endpoint="http://<host>:6006/v1/traces")`. Or set `PHOENIX_COLLECTOR_ENDPOINT=http://<host>:6006/v1/traces`.
**Warning signs:** No traces appearing in Phoenix UI despite no exceptions in Python code.

### Pitfall 2: TracerProvider Initialized After First Span
**What goes wrong:** Early pipeline spans (e.g., from APScheduler) use the no-op tracer and are lost.
**Why it happens:** `register()` sets the global TracerProvider — any `trace.get_tracer()` call before it returns a no-op.
**How to avoid:** Call `init_tracing()` at the top of FastAPI lifespan startup, before APScheduler starts. In `tracer.py`, add a guard: if `PHOENIX_COLLECTOR_ENDPOINT` not set, log a warning and skip (for test environments).
**Warning signs:** First trace of the day is missing; subsequent runs visible.

### Pitfall 3: Subprocess Span Timing
**What goes wrong:** `invoke_claude()` span duration is accurate but child spans inside the Claude CLI process are not captured.
**Why it happens:** `subprocess.run()` launches a separate process; OTel context does not cross process boundaries without explicit W3C trace-context header injection.
**How to avoid:** Do not try to instrument inside the Claude CLI process — just wrap the `subprocess.run()` call itself. The span duration covers the full CLI invocation latency, which is the correct metric.

### Pitfall 4: Full Prompt/Response Payload Size
**What goes wrong:** Large prompts (>100KB) cause OTLP export failures or Phoenix storage issues.
**Why it happens:** OTLP has a default 4MB per-batch limit; very large payloads can push individual spans over limits.
**How to avoid:** Truncate `INPUT_VALUE` and `OUTPUT_VALUE` to a safe limit (e.g., 32KB) before setting as span attribute. Log a `truncated=True` attribute alongside.

### Pitfall 5: Tests Import Tracer Before register()
**What goes wrong:** Test suite crashes or produces warnings about no TracerProvider configured.
**Why it happens:** Importing pipeline modules that call `trace.get_tracer()` at module level will use the no-op provider — harmless — but if tests assert on span data they'll get nothing.
**How to avoid:** In `conftest.py`, initialize an in-memory `TracerProvider` with `InMemorySpanExporter` for tests. Pipeline code works unchanged; tests can assert on captured spans.

---

## Code Examples

### Startup Initialization (FastAPI lifespan)
```python
# src/api/main.py or lifespan handler
# Source: https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel
import os
from src.runtime.tracer import init_tracing

@asynccontextmanager
async def lifespan(app: FastAPI):
    endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
    init_tracing(endpoint=endpoint, project_name="meridian")
    yield
```

### In-Memory Tracer for Tests
```python
# tests/conftest.py addition
# Source: opentelemetry-sdk docs
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry import trace

@pytest.fixture(autouse=True)
def otel_tracer():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()
```

### Stage Span with Error Handling
```python
# Source: opentelemetry-api docs — StatusCode pattern
from opentelemetry import trace
from opentelemetry.trace import StatusCode

tracer = trace.get_tracer("meridian.pipeline")

with tracer.start_as_current_span("meridian.stage.scout") as span:
    try:
        result = run_scout_logic()
        span.set_attribute("scout.papers_fetched", result.paper_count)
        span.set_status(StatusCode.OK)
    except Exception as e:
        span.record_exception(e)
        span.set_status(StatusCode.ERROR, str(e))
        raise
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `opentelemetry-exporter-jaeger` | OTLP HTTP/gRPC to Phoenix | 2023+ | Phoenix is the AI-native backend; Jaeger has no LLM-specific views |
| Manual HTTP requests to Phoenix API | `arize-phoenix-otel` `register()` | 2024 | register() handles batching, retry, protocol negotiation |
| `openinference-instrumentation-langchain` auto-instrumentation | Manual spans (no framework) | N/A for this project | Meridian uses subprocess Claude CLI — no framework to auto-instrument |

---

## Open Questions

1. **Phoenix Docker network address from VPS Python process**
   - What we know: Phoenix runs as a Docker container on the same VPS
   - What's unclear: Whether Phoenix is on `localhost:6006`, a Docker network IP, or a domain
   - Recommendation: Use `PHOENIX_COLLECTOR_ENDPOINT` env var; set it in `.env` on VPS deployment

2. **Data retention / trace cleanup**
   - What we know: Phoenix stores traces in SQLite by default; no automatic TTL
   - What's unclear: Whether the VPS Phoenix instance has storage constraints
   - Recommendation: Start without cleanup; revisit after 30 days of data. Phoenix supports `--storage-path` for external volumes.

3. **APScheduler entry point vs. webhook entry point**
   - What we know: Both trigger the same pipeline; both need a root span
   - What's unclear: Whether they share the same pipeline entry function or branch early
   - Recommendation: Create a single `run_pipeline(trigger: str)` function that opens the root span — both scheduler and webhook call it.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `/Users/a.christuraj/Projects/meridian/pytest.ini` |
| Quick run command | `pytest tests/test_claude_runner.py tests/test_scout.py -x` |
| Full suite command | `pytest tests/` |

### Phase Requirements → Test Map

| ID | Behavior | Test Type | Automated Command | File Exists? |
|----|----------|-----------|-------------------|-------------|
| OBS-01 | `init_tracing()` sets global TracerProvider without error | unit | `pytest tests/test_tracer.py::test_init_tracing -x` | Wave 0 |
| OBS-02 | `invoke_claude()` creates span with LLM token/cost attributes | unit | `pytest tests/test_claude_runner.py::test_invoke_claude_span -x` | Wave 0 |
| OBS-03 | Pipeline root span contains four child stage spans | integration | `pytest tests/test_pipeline_tracing.py::test_pipeline_span_structure -x` | Wave 0 |
| OBS-04 | Each stage span records correct business metric attributes | unit | `pytest tests/test_pipeline_tracing.py::test_stage_attributes -x` | Wave 0 |
| OBS-05 | Stage span captures exception via `record_exception` on failure | unit | `pytest tests/test_pipeline_tracing.py::test_stage_error_span -x` | Wave 0 |
| OBS-06 | Existing heartbeat files still written (no regression) | integration | `pytest tests/test_scout.py tests/test_briefing.py tests/test_translator.py -x` | ✅ |
| OBS-07 | Traces appear in Phoenix UI (smoke — manual verification) | manual | N/A | manual-only |

**OBS-07 is manual-only** because it requires the live Phoenix Docker endpoint on the VPS.

### Sampling Rate
- **Per task commit:** `pytest tests/test_tracer.py tests/test_claude_runner.py -x`
- **Per wave merge:** `pytest tests/`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_tracer.py` — covers OBS-01; needs `InMemorySpanExporter` fixture
- [ ] `tests/test_pipeline_tracing.py` — covers OBS-03, OBS-04, OBS-05
- [ ] `tests/conftest.py` — add `otel_tracer` autouse fixture with `InMemorySpanExporter`
- [ ] Add OBS-02 test case to existing `tests/test_claude_runner.py`
- [ ] Add to `requirements.txt`: `arize-phoenix-otel`, `openinference-semantic-conventions`, `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`

---

## Sources

### Primary (HIGH confidence)
- [arize-phoenix-otel PyPI](https://pypi.org/project/arize-phoenix-otel/) — version 0.15.0, install command
- [Setup OTEL - Phoenix docs](https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel) — `register()` function, endpoint config, HTTP vs gRPC ports
- [OpenInference Semantic Conventions](https://arize-ai.github.io/openinference/spec/semantic_conventions.html) — `SpanAttributes` constants for LLM token counts, cost, model, input/output

### Secondary (MEDIUM confidence)
- [Phoenix OTEL Reference 0.15.0](https://arize-phoenix.readthedocs.io/projects/otel/) — `register()` signature and `batch` parameter
- [Using Tracing Helpers - Phoenix](https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/instrument) — manual span creation patterns

### Tertiary (LOW confidence)
- WebSearch results on `PHOENIX_COLLECTOR_ENDPOINT` env var behavior — cross-referenced with PyPI README

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified via PyPI (version 0.15.0, March 2026) and official Phoenix docs
- Architecture: HIGH — OTel context propagation is standard; Phoenix OTEL patterns verified from official docs
- Pitfalls: MEDIUM — port confusion and payload size verified from docs; test isolation pattern is standard OTel SDK practice
- Validation architecture: HIGH — test infrastructure scanned directly from repo

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (arize-phoenix-otel releases frequently; recheck version before install)
