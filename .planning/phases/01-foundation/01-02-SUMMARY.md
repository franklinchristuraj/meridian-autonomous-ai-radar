---
phase: 01-foundation
plan: 02
subsystem: api, runtime
tags: [fastapi, auth, subprocess, tdd]
dependency_graph:
  requires: []
  provides: [trigger-endpoint, claude-runner]
  affects: [phase-2-scout]
tech_stack:
  added: [fastapi, python-dotenv, httpx]
  patterns: [APIKeyHeader security dependency, BackgroundTasks, subprocess wrapper]
key_files:
  created:
    - src/api/main.py
    - src/api/auth.py
    - src/api/routes/trigger.py
    - src/runtime/claude_runner.py
    - tests/test_trigger.py
    - tests/test_claude_runner.py
  modified: []
decisions:
  - "APIKeyHeader auto_error=False used so missing key returns 403 (not 401)"
  - "invoke_claude uses subprocess.run with capture_output for clean mocking in tests"
metrics:
  duration: ~30min
  completed_date: "2026-03-14"
  tasks_completed: 2
  files_created: 6
---

# Phase 1 Plan 2: FastAPI Trigger Endpoint and Claude Runner Summary

**One-liner:** FastAPI app with X-API-Key authenticated POST /pipeline/trigger (202) and Claude Code CLI subprocess wrapper with JSON parsing.

## What Was Built

### Task 1: FastAPI trigger endpoint with shared-secret auth

- `src/api/auth.py` — `verify_api_key` dependency using `APIKeyHeader(auto_error=False)` so both missing and invalid keys return 403 consistently.
- `src/api/routes/trigger.py` — `POST /pipeline/trigger` (202) with `BackgroundTasks` stub calling `run_scout_pipeline()`.
- `src/api/main.py` — FastAPI app with lifespan, trigger router, and `GET /health`.
- 3 tests pass: valid key → 202, bad key → 403, missing key → 403.

### Task 2: Claude Code CLI subprocess wrapper

- `src/runtime/claude_runner.py` — `invoke_claude(prompt, model, timeout)` calls `claude -p --output-format json --model <model>`, raises `RuntimeError` on non-zero exit, raises `JSONDecodeError` on invalid output.
- 3 tests pass with mocked subprocess (no local CLI required).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] APIKeyHeader returns 401 for missing key instead of 403**
- **Found during:** Task 1 GREEN verification
- **Issue:** `APIKeyHeader(auto_error=True)` triggers FastAPI's default 401 response when the header is absent, but tests (and plan spec) expect 403 for all invalid/missing key cases.
- **Fix:** Changed to `auto_error=False` and added explicit `if not key` check in `verify_api_key`, normalizing all auth failures to 403.
- **Files modified:** `src/api/auth.py`
- **Commit:** 36269fb (included in GREEN commit)

## Verification

```
pytest tests/test_trigger.py tests/test_claude_runner.py -v
6 passed in 0.20s
```

App imports cleanly:
```
python -c "from src.api.main import app; print(app.title)"
Meridian Pipeline
```

## Commits

| Hash    | Message                                              |
|---------|------------------------------------------------------|
| 7ea30bb | test(01-02): add failing tests for trigger endpoint  |
| 36269fb | feat(01-02): FastAPI trigger endpoint with shared-secret auth |
| 199591f | test(01-02): add failing tests for Claude CLI subprocess wrapper |
| 7889b3f | feat(01-02): Claude Code CLI subprocess wrapper      |

## Self-Check: PASSED
