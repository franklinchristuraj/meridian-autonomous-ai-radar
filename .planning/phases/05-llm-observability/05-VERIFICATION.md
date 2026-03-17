---
phase: 05-llm-observability
verified: 2026-03-17T00:00:00Z
status: human_needed
score: 11/12 must-haves verified
human_verification:
  - test: "Trigger a live pipeline run on the VPS and open Phoenix UI at http://your-vps:6006"
    expected: "Trace named 'meridian.stage.scout' appears with child invoke_claude spans showing llm.model_name, llm.token_count.prompt, llm.cost_usd attributes; full pipeline chain scout -> analyst -> briefing -> translator is visible"
    why_human: "OBS-07 requires a live Phoenix Docker endpoint on VPS — cannot verify programmatically"
---

# Phase 05: LLM Observability Verification Report

**Phase Goal:** Phoenix dashboards for token cost monitoring, latency tracking, and pipeline performance visibility
**Verified:** 2026-03-17
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | `init_tracing()` sets a global TracerProvider that produces real spans | VERIFIED | `src/runtime/tracer.py:21` — `def init_tracing()` calls `phoenix.otel.register()` |
| 2  | Tests can capture spans via InMemorySpanExporter without hitting Phoenix | VERIFIED | `tests/conftest.py:8-15` — `autouse=True` fixture yields `InMemorySpanExporter` |
| 3  | OTel dependencies are declared in requirements.txt | VERIFIED | `requirements.txt:11-15` — all 5 packages present |
| 4  | `invoke_claude()` creates an LLM span with token counts, cost, model, and input/output payloads | VERIFIED | `src/runtime/claude_runner.py:29-79` — `start_as_current_span("invoke_claude")` with `LLM_MODEL_NAME`, `LLM_TOKEN_COUNT_PROMPT`, `llm.cost_usd`, `INPUT_VALUE`, `OUTPUT_VALUE`, `prompt[:32768]` |
| 5  | Each pipeline stage creates a named child span under the root | VERIFIED | scout:275, analyst:187, briefing:263, translator:254 — all use `start_as_current_span("meridian.stage.*")` |
| 6  | Stage spans record business metric attributes | VERIFIED | `scout.papers_fetched`, `scout.signals_scored`, `analyst.clusters_found`, `briefing.signals_processed`, `translator.seeds_deposited` all present |
| 7  | Existing heartbeat files are still written (no regression) | VERIFIED | `TestHeartbeatRegression` class in `tests/test_pipeline_tracing.py:173` asserts `mock_hb_path.write_text.assert_called_once()` |
| 8  | Pipeline errors are captured via `span.record_exception()` | VERIFIED | All 5 modules have `record_exception(e)` + `set_status(StatusCode.ERROR)` in except blocks |
| 9  | `init_tracing()` is called at FastAPI startup before APScheduler starts | VERIFIED | `src/api/main.py:25` — `init_tracing()` at line 25, `scheduler.start()` at line 38 |
| 10 | `PHOENIX_COLLECTOR_ENDPOINT` env var controls the trace destination | VERIFIED | `src/runtime/tracer.py` reads env var; `.env.example:12` documents `PHOENIX_COLLECTOR_ENDPOINT=https://phoenix.ziksaka.com/v1/traces` |
| 11 | Test suite fully covers OBS-01 through OBS-06 with passing tests | VERIFIED | `tests/test_tracer.py` (92 lines, 5 tests), `tests/test_pipeline_tracing.py` (203 lines, 6 test classes), `tests/test_claude_runner.py::TestInvokeClaudeSpan` |
| 12 | Traces appear in Phoenix UI when pipeline runs on VPS | NEEDS HUMAN | OBS-07 is manual-only — requires live Phoenix Docker endpoint |

**Score:** 11/12 truths verified (1 needs human confirmation)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/runtime/tracer.py` | Centralized tracer init module | VERIFIED | 65 lines; exports `init_tracing`, `tracer`, `StatusCode`; calls `phoenix.otel.register()` |
| `tests/conftest.py` | InMemorySpanExporter autouse fixture | VERIFIED | 54 lines; `autouse=True` fixture yields exporter |
| `tests/test_tracer.py` | Unit tests for tracer init | VERIFIED | 92 lines (min 20); 5 test functions |
| `src/runtime/claude_runner.py` | LLM span instrumentation | VERIFIED | `start_as_current_span("invoke_claude")` with full LLM attributes |
| `src/pipeline/scout.py` | Scout stage span | VERIFIED | `meridian.stage.scout` span with `papers_fetched`, `signals_scored` |
| `src/pipeline/analyst.py` | Analyst stage span | VERIFIED | `meridian.stage.analyst` span with `clusters_found` |
| `src/pipeline/briefing.py` | Briefing stage span | VERIFIED | `meridian.stage.briefing` span with `signals_processed`, `clusters_generated` |
| `src/pipeline/translator.py` | Translator stage span | VERIFIED | `meridian.stage.translator` span with `seeds_deposited` |
| `tests/test_pipeline_tracing.py` | Pipeline tracing integration tests | VERIFIED | 203 lines (min 50); 6 test classes |
| `src/api/main.py` | Tracing init in FastAPI lifespan | VERIFIED | `init_tracing()` at line 25, before `scheduler.start()` at line 38 |
| `.env.example` | Documents PHOENIX_COLLECTOR_ENDPOINT | VERIFIED | Line 12: `PHOENIX_COLLECTOR_ENDPOINT=https://phoenix.ziksaka.com/v1/traces` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/runtime/tracer.py` | `phoenix.otel` | `register()` call | WIRED | `from phoenix.otel import register` present (lazy import inside try block at line 49) |
| `tests/conftest.py` | `opentelemetry.sdk.trace` | `InMemorySpanExporter` fixture | WIRED | Import + fixture definition confirmed |
| `src/runtime/claude_runner.py` | `openinference.semconv.trace.SpanAttributes` | LLM attribute constants | WIRED | `SpanAttributes.LLM_MODEL_NAME`, `LLM_TOKEN_COUNT_PROMPT` etc. all present |
| `src/pipeline/scout.py` | `src/runtime/tracer` | tracer import | WIRED | Uses `trace.get_tracer("meridian.pipeline")` inline (equivalent — no module-level `_tracer`) |
| `src/pipeline/briefing.py` | `src/runtime/tracer` | tracer import | WIRED | Uses `trace.get_tracer("meridian.pipeline")` inline |
| `src/api/main.py` | `src/runtime/tracer` | `init_tracing()` in lifespan | WIRED | `from src.runtime.tracer import init_tracing` + called before scheduler |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| OBS-01 | 05-01 | Phoenix dashboards for LLM tracing (token usage, latency, cost per signal) | SATISFIED | `init_tracing()` + `tracer.py` foundation established |
| OBS-02 | 05-02 | `invoke_claude()` creates span with LLM token/cost attributes | SATISFIED | `TestInvokeClaudeSpan` verifies `llm.token_count.prompt`, `llm.cost_usd`, `input.value` etc. |
| OBS-03 | 05-02 | Pipeline root span contains four child stage spans | SATISFIED | All 4 stage spans created via `start_as_current_span`; `TestScoutSpan`, `TestBriefingSpan` etc. cover this |
| OBS-04 | 05-02 | Each stage span records correct business metric attributes | SATISFIED | `TestAnalystSpan` asserts `analyst.clusters_found==1`; all business attrs verified |
| OBS-05 | 05-01, 05-02 | Stage span captures exception via `record_exception` on failure | SATISFIED | `test_span_records_exception_on_error` + `test_scout_span_error` both verify ERROR status + exception event |
| OBS-06 | 05-02 | Existing heartbeat files still written (no regression) | SATISFIED | `TestHeartbeatRegression.test_scout_heartbeat_still_written` asserts `write_text.assert_called_once()` |
| OBS-07 | 05-03 | Traces appear in Phoenix UI (manual verification) | NEEDS HUMAN | Plan 03 Task 2 is `checkpoint:human-verify gate:blocking`; code wiring is complete |

### Anti-Patterns Found

None detected. No TODO/FIXME/placeholder comments in modified source files. No stub implementations. No empty returns. No console.log-only handlers.

### Human Verification Required

#### 1. Phoenix UI Smoke Test (OBS-07)

**Test:** On the VPS, ensure `PHOENIX_COLLECTOR_ENDPOINT` is set in `.env`, start the FastAPI app with `uvicorn src.api.main:app`, trigger a pipeline run via `curl -X POST http://localhost:8000/trigger`, then open Phoenix UI.

**Expected:**
- A trace named `meridian.stage.scout` appears with child `invoke_claude` spans
- Clicking an `invoke_claude` span shows `llm.model_name`, `llm.token_count.prompt`, `llm.cost_usd` attributes
- Stage spans show business metrics (`scout.papers_fetched`, `analyst.clusters_found`, etc.)
- Full pipeline chain is visible: scout -> analyst -> briefing -> translator
- Heartbeat files still written: `cat heartbeat/scout.json` shows recent timestamp

**Why human:** Requires a live Phoenix Docker endpoint on VPS. Cannot be verified programmatically from local environment.

### Gaps Summary

No automated gaps. All 11 programmatically verifiable must-haves pass at all three levels (exists, substantive, wired). One item (OBS-07) is inherently manual by design — the plan itself marks it as `checkpoint:human-verify gate:blocking`.

---

_Verified: 2026-03-17_
_Verifier: Claude (gsd-verifier)_
