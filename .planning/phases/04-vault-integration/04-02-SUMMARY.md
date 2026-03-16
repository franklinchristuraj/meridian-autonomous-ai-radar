---
phase: 04-vault-integration
plan: 02
subsystem: api-vault
tags: [fastapi, vault, translator, chain-wiring, routes]
dependency_graph:
  requires: ["04-01"]
  provides: ["vault-api-routes", "briefing-translator-chain"]
  affects: ["src/api/main.py", "src/pipeline/briefing.py"]
tech_stack:
  added: []
  patterns: ["lazy-import-wrapper", "BackgroundTasks", "APIRouter", "chain-trigger"]
key_files:
  created:
    - src/api/routes/vault.py
    - tests/test_vault_routes.py
  modified:
    - src/api/main.py
    - src/pipeline/briefing.py
    - tests/test_briefing.py
decisions:
  - "Vault route tests patch at src.pipeline.translator (canonical module) not src.api.routes.vault — lazy imports inside route handlers resolve at call time"
  - "Existing test_run_analyst_briefing_pipeline patched to mock _run_translator_pipeline — new chain call would otherwise fail without OBSIDIAN_VAULT_PATH env var in test environment"
  - "_run_translator_pipeline() placed inside try block so translator errors propagate cleanly via existing finally clause"
metrics:
  duration_minutes: 3
  completed_date: "2026-03-16"
  tasks_completed: 2
  files_changed: 5
---

# Phase 4 Plan 2: Vault API Routes and Briefing-Translator Chain Summary

Vault API routes (POST /vault/deposit, GET /vault/deposits) wired into FastAPI with BackgroundTasks trigger and X-API-Key auth; briefing pipeline chains to Translator via lazy-import wrapper on completion.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Vault API routes + tests (TDD) | 537044a | src/api/routes/vault.py, tests/test_vault_routes.py |
| 2 | Router registration + Briefing chain wiring | 863724e | src/api/main.py, src/pipeline/briefing.py, tests/test_briefing.py |

## What Was Built

**Task 1 — Vault API routes (TDD RED/GREEN)**

- `src/api/routes/vault.py`: Two routes under `/vault` prefix
  - `POST /vault/deposit` — triggers `run_translator_pipeline` via `BackgroundTasks`, requires `X-API-Key` (403 without), returns 202
  - `GET /vault/deposits` — scans `01_seeds/*.md` for `auto_deposit: true` frontmatter, returns list with title, created, signal_uuid, arxiv_url, confidence; filters by `days` param (default 30)
- `tests/test_vault_routes.py`: 5 tests — 202 response, 403 auth, empty list, 2-seed list with required keys, non-auto-deposit filtering

**Task 2 — Router registration + chain wiring**

- `src/api/main.py`: Added `vault_router` import and `app.include_router(vault_router)`
- `src/pipeline/briefing.py`: Added `_run_translator_pipeline()` lazy-import wrapper; called at tail of `run_analyst_briefing_pipeline()` inside try block after `write_briefing_heartbeat()`
- `tests/test_briefing.py`: Added `test_briefing_triggers_translator` asserting `_run_translator_pipeline` called once on successful pipeline run; patched new chain call in existing orchestration test

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Patch target for lazy-import route handlers**
- **Found during:** Task 1 GREEN phase
- **Issue:** Test patched `src.api.routes.vault.run_translator_pipeline` but the route uses a lazy import inside the function body — the attribute doesn't exist on the vault module at patch time
- **Fix:** Patched at canonical location `src.pipeline.translator.run_translator_pipeline` (and `get_vault_seeds_path`) — correct target for lazy imports resolved at call time
- **Files modified:** tests/test_vault_routes.py
- **Commit:** 537044a

**2. [Rule 1 - Bug] Existing pipeline test broke after chain wiring**
- **Found during:** Task 2 verification
- **Issue:** `test_run_analyst_briefing_pipeline` called real `_run_translator_pipeline()` after chain was added, which tried to call `get_vault_seeds_path()` and raised `EnvironmentError` (OBSIDIAN_VAULT_PATH not set in test env)
- **Fix:** Added `patch("src.pipeline.briefing._run_translator_pipeline")` to existing test mock context
- **Files modified:** tests/test_briefing.py
- **Commit:** 863724e

## Verification

```
.venv/bin/python -m pytest tests/ -x
116 passed in 33.40s
```

All 116 tests pass including 5 new vault route tests and 1 new briefing chain test.

## Self-Check: PASSED

- [x] src/api/routes/vault.py exists
- [x] tests/test_vault_routes.py exists (149 lines, 5 tests)
- [x] src/api/main.py contains vault_router
- [x] src/pipeline/briefing.py contains _run_translator_pipeline
- [x] Commit 537044a exists
- [x] Commit 863724e exists
