---
phase: 05-llm-observability
plan: 02
subsystem: observability
tags: [tracing, opentelemetry, openinference, pipeline, llm]
dependency_graph:
  requires: [05-01]
  provides: [OBS-02, OBS-03, OBS-04, OBS-05, OBS-06]
  affects: [src/runtime/claude_runner.py, src/pipeline/scout.py, src/pipeline/analyst.py, src/pipeline/briefing.py, src/pipeline/translator.py]
tech_stack:
  added: []
  patterns: [lazy-tracer-per-call, openinference-semconv, record_exception]
key_files:
  created:
    - tests/test_pipeline_tracing.py
  modified:
    - src/runtime/claude_runner.py
    - src/pipeline/scout.py
    - src/pipeline/analyst.py
    - src/pipeline/briefing.py
    - src/pipeline/translator.py
    - tests/test_claude_runner.py
decisions:
  - "Use trace.get_tracer() at call time (not module-level) so test fixtures can reset the global provider per test"
  - "Truncate LLM input/output to 32KB in spans to avoid OTLP export size issues"
metrics:
  duration: ~20min
  completed: 2026-03-16
  tasks_completed: 2
  files_touched: 7
  tests_added: 7
  tests_total: 128
---

# Phase 05 Plan 02: Pipeline Instrumentation Summary

**One-liner:** LLM span on invoke_claude() with token/cost attributes + named stage spans on all four pipeline stages recording business metrics, verified by 7 new tracing tests.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Instrument invoke_claude + 4 pipeline stages | b4a585b | claude_runner.py, scout.py, analyst.py, briefing.py, translator.py |
| 2 | Pipeline tracing tests + invoke_claude span test | f56a193 | test_pipeline_tracing.py, test_claude_runner.py (+ fix tracer pattern) |

## What Was Built

### invoke_claude() LLM Span (OBS-02)
- Span name: `invoke_claude` under tracer `meridian.llm`
- Attributes: `openinference.span.kind=LLM`, `llm.model_name`, `llm.token_count.prompt`, `llm.token_count.completion`, `llm.token_count.total`, `llm.cost_usd`, `input.value` (32KB truncated), `output.value` (32KB truncated)
- Error recording: `span.record_exception()` + `StatusCode.ERROR` on CLI failure

### Pipeline Stage Spans (OBS-03, OBS-04)

| Stage | Span Name | Business Attributes |
|-------|-----------|---------------------|
| Scout | `meridian.stage.scout` | papers_fetched, papers_filtered, signals_scored, last_error |
| Analyst | `meridian.stage.analyst` | signals_count, history_count, clusters_found, singletons_count |
| Briefing | `meridian.stage.briefing` | signals_processed, clusters_generated, items_generated |
| Translator | `meridian.stage.translator` | vault_signals_found, candidates, seeds_deposited |

### Error Recording (OBS-05)
All stages wrap body in try/except: `span.record_exception(e)` + `span.set_status(StatusCode.ERROR, str(e))`.

### Heartbeat Regression (OBS-06)
Heartbeat writes remain inside span context — write_heartbeat calls unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed lazy tracer pattern for test isolation**
- **Found during:** Task 2 (2 tests failing)
- **Issue:** Module-level `_tracer = trace.get_tracer(...)` captures the tracer at import time, before the `otel_test_provider` fixture resets the global provider. The cached ProxyTracer delegates to the old (no-op) provider, so spans were never recorded in tests.
- **Fix:** Replaced all `_tracer.start_as_current_span(...)` calls with `trace.get_tracer("meridian.pipeline").start_as_current_span(...)` inline — i.e., get a fresh tracer each time the function runs. Also removed the module-level `_tracer` variable from all 4 pipeline files and `claude_runner.py`.
- **Files modified:** All 5 instrumented modules
- **Commit:** f56a193

**2. [Rule 1 - Bug] Fixed subprocess.run patch path in existing tests**
- **Found during:** Task 2
- **Issue:** Existing tests in `test_claude_runner.py` patched `subprocess.run` (global) instead of `src.runtime.claude_runner.subprocess.run`. After adding the span wrapper, the mock wasn't intercepting the call correctly.
- **Fix:** Updated all 3 existing test patch targets to `src.runtime.claude_runner.subprocess.run`.
- **Files modified:** tests/test_claude_runner.py
- **Commit:** f56a193

## Test Results

- **Before:** 121 tests passing
- **After:** 128 tests passing (+7 new)
- New tests cover: OBS-02 (LLM span), OBS-03 (stage spans), OBS-04 (business metrics), OBS-05 (error spans), OBS-06 (heartbeat regression)

## Self-Check: PASSED

Files verified:
- src/runtime/claude_runner.py — contains `start_as_current_span("invoke_claude")`, `SpanAttributes.LLM_TOKEN_COUNT_PROMPT`, `prompt[:32768]`
- src/pipeline/scout.py — contains `start_as_current_span("meridian.stage.scout")`, `scout.papers_fetched`, `scout.signals_scored`
- src/pipeline/analyst.py — contains `start_as_current_span("meridian.stage.analyst")`, `analyst.clusters_found`
- src/pipeline/briefing.py — contains `start_as_current_span("meridian.stage.briefing")`, `briefing.signals_processed`
- src/pipeline/translator.py — contains `start_as_current_span("meridian.stage.translator")`, `translator.seeds_deposited`
- tests/test_pipeline_tracing.py — created, 6 tests
- tests/test_claude_runner.py — contains `TestInvokeClaudeSpan`, 1 new test

Commits verified: b4a585b, f56a193
