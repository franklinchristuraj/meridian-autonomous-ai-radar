---
phase: 03-intelligence-briefing
plan: 02
subsystem: api
tags: [fastapi, weaviate, claude-sonnet, briefing, pipeline, tdd]

# Dependency graph
requires:
  - phase: 03-01
    provides: cluster_signals, write_cluster_ids, fetch_todays_signals, fetch_recent_signals from analyst.py
  - phase: 02-scout-pipeline
    provides: run_scout_pipeline, invoke_claude, get_client
provides:
  - generate_briefing_narrative: Sonnet-powered structured narrative with executive summary + 10 items
  - write_briefing: Idempotent write to Briefings collection with date deduplication
  - run_analyst_briefing_pipeline: Full Analyst+Briefing orchestrator with concurrency guard
  - POST /briefing/generate: Manual pipeline trigger with API key auth
  - GET /briefing/today/narrative: Today's briefing narrative text + staleness info
  - GET /briefing/today/data: Today's structured items JSON + staleness info
  - GET /briefing/{date}/narrative: Historical narrative endpoint
  - GET /briefing/{date}/data: Historical data endpoint
affects: [03-03, phase-04-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TDD red-green cycle with @patch decorator stacking for pipeline mocks
    - Lazy import wrapper function (_run_briefing_pipeline) for circular-import-safe wiring
    - Date deduplication via delete+reinsert (not upsert) matching existing project idiom
    - Staleness detection via heartbeat file age (>25h threshold)

key-files:
  created:
    - src/pipeline/briefing.py
    - src/api/routes/briefing.py
    - tests/test_briefing.py
    - tests/test_briefing_routes.py
  modified:
    - src/pipeline/scout.py
    - src/api/main.py
    - tests/test_scout.py

key-decisions:
  - "Briefing pipeline wrapped in _run_briefing_pipeline() in scout.py to allow clean @patch isolation in existing scout tests without circular import at module level"
  - "generate_briefing_narrative enforces BRIEF-first ordering and 10-item cap client-side (not relying on Sonnet to do it)"
  - "write_briefing uses delete+reinsert for date deduplication, consistent with existing idempotency patterns in the codebase"
  - "Staleness threshold is 25 hours (not 24) to allow for slight scheduling drift without false stale flags"

patterns-established:
  - "Pipeline lazy import wrapper: def _run_X(): from src.pipeline.X import run_X; run_X() — enables @patch('src.module._run_X') in tests"
  - "Route helper functions (get_briefing_staleness, get_briefing_for_date) defined before router so they can be monkeypatched in route tests"

requirements-completed: [DELIV-01]

# Metrics
duration: 35min
completed: 2026-03-15
---

# Phase 3 Plan 02: Briefing Agent Summary

**Sonnet-powered morning briefing agent generating structured narratives (executive summary + 10 tiered items) from Analyst clusters, with Scout wiring and 5 FastAPI read/trigger endpoints**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-03-15T18:57:00Z
- **Completed:** 2026-03-15T19:32:00Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 6

## Accomplishments

- Briefing pipeline module with Sonnet narrative generation, regex fallback, BRIEF-first sort, 10-item cap, date deduplication, and concurrency guard
- Scout pipeline wired to trigger Analyst+Briefing at end of each successful run
- 5 FastAPI endpoints for briefing trigger and read with staleness detection
- 86/86 total tests passing (19 new briefing tests + 67 existing)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing briefing pipeline tests** — `ff8f3e2` (test)
2. **Task 1 GREEN: Briefing pipeline + Scout wiring** — `ebe26ae` (feat)
3. **Task 2 RED: Failing briefing route tests** — `5b84768` (test)
4. **Task 2 GREEN: Briefing API routes + main.py + scout fix** — `1ffc155` (feat)

## Files Created/Modified

- `src/pipeline/briefing.py` — generate_briefing_narrative, write_briefing, write_briefing_heartbeat, run_analyst_briefing_pipeline
- `src/api/routes/briefing.py` — 5 endpoints: POST /generate, GET /today/narrative, GET /today/data, GET /{date}/narrative, GET /{date}/data
- `src/api/main.py` — added include_router(briefing_router)
- `src/pipeline/scout.py` — added _run_briefing_pipeline() wrapper, called at end of run_scout_pipeline
- `tests/test_briefing.py` — 9 tests for pipeline module
- `tests/test_briefing_routes.py` — 10 tests for API routes + staleness detection
- `tests/test_scout.py` — 3 existing pipeline tests updated to mock _run_briefing_pipeline

## Decisions Made

- **Lazy import wrapper in scout.py:** The briefing call is wrapped in `_run_briefing_pipeline()` which does the import internally. This allows existing scout tests to patch `src.pipeline.scout._run_briefing_pipeline` without any module-level circular import risk.
- **BRIEF-first sort enforced client-side:** `_sort_and_cap_items()` explicitly reorders items after Sonnet response rather than relying on prompt instruction, ensuring the guarantee holds regardless of model output ordering.
- **Staleness threshold 25h:** Gives a 1-hour buffer over 24h so daily briefings don't show stale when Scout runs slightly late.
- **Date deduplication via delete+reinsert:** Matches the project's existing idempotency pattern (name-match lookup then delete/insert, not upsert).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Scout pipeline test isolation broken by briefing wiring**
- **Found during:** Task 2 verification (full suite run)
- **Issue:** After adding `run_analyst_briefing_pipeline()` call to `run_scout_pipeline`, the existing `test_run_scout_pipeline_happy_path` (and 2 similar tests) failed because the real briefing function called `get_client()` which attempted `claude` CLI invocation
- **Fix:** Wrapped briefing call in `_run_briefing_pipeline()` in scout.py; added `@patch("src.pipeline.scout._run_briefing_pipeline")` to the 3 affected tests
- **Files modified:** src/pipeline/scout.py, tests/test_scout.py
- **Verification:** 86/86 tests pass
- **Committed in:** `1ffc155` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Essential fix for test isolation. No scope creep. The wrapper pattern is now established for future pipeline chaining.

## Issues Encountered

None beyond the scout test isolation issue documented above.

## Next Phase Readiness

- Full pipeline wired end-to-end: Scout -> Analyst -> Briefing -> Weaviate -> API
- 5 briefing endpoints ready for Plan 03-03 (delivery/Obsidian integration)
- Heartbeat-based staleness detection operational
- 86 tests passing as green baseline for Phase 3 completion

---
*Phase: 03-intelligence-briefing*
*Completed: 2026-03-15*
