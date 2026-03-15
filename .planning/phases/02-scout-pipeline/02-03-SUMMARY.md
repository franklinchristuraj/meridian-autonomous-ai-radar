---
phase: 02-scout-pipeline
plan: "03"
subsystem: pipeline
tags: [gap-closure, scheduler, ingest, trigger, apscheduler]
dependency_graph:
  requires: [02-01, 02-02]
  provides: [manual-seed-ingestion, apscheduler-cron]
  affects: [src/api/main.py, src/api/routes/trigger.py, src/pipeline/ingest.py]
tech_stack:
  added: [apscheduler>=3.10]
  patterns: [TDD, background-tasks, cron-scheduler, pydantic-models]
key_files:
  created:
    - src/pipeline/ingest.py
    - tests/test_ingest.py
  modified:
    - src/api/routes/trigger.py
    - src/api/main.py
    - tests/test_trigger.py
    - requirements.txt
decisions:
  - "APScheduler 3.x (AsyncIOScheduler) chosen over Celery/ARQ — lightweight, asyncio-native, no broker needed for single-job cron"
  - "Manual seeds default to tier=BRIEF so they always surface in daily briefings — user intent is attention, not scoring"
  - "Deduplication in ingest_manual_seed uses source_url filter (not arxiv_id) since manual seeds may not have arxiv IDs"
metrics:
  duration: ~20min
  completed: "2026-03-15"
  tasks_completed: 2
  files_changed: 6
  tests_added: 11
  total_tests: 50
---

# Phase 02 Plan 03: Trigger/Scheduler Separation (Gap Closure) Summary

**One-liner:** Split manual seed ingestion (HTTP trigger) from daily ArXiv Scout (APScheduler cron at 06:00 UTC) into two fully independent flows.

## What Was Built

Closed GAP-01: the trigger endpoint previously called `run_scout_pipeline` directly, conflating two distinct flows. This plan separates them cleanly.

**Flow 1 — Manual seeds via HTTP:**
- `src/pipeline/ingest.py` — `ingest_manual_seed(data: dict) -> str` writes a Signal with `status="manual"`, `tier="BRIEF"`, `score=0.0`; deduplicates by `source_url`; uses try/finally for Weaviate lifecycle
- `src/api/routes/trigger.py` — Pydantic `SeedPayload` model (title required, url/notes/abstract optional); calls `ingest_manual_seed` in BackgroundTasks; auth unchanged

**Flow 2 — Daily ArXiv via cron:**
- `src/api/main.py` — APScheduler `AsyncIOScheduler` starts in FastAPI lifespan, schedules `run_scout_pipeline` at `SCOUT_CRON_HOUR:SCOUT_CRON_MINUTE` (default 06:00 UTC); shuts down cleanly on app teardown

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Manual seed ingestion + trigger rewrite | df601c3 | src/pipeline/ingest.py, src/api/routes/trigger.py |
| 1 (RED) | Failing tests for ingest + trigger | 4ff0d6c | tests/test_ingest.py, tests/test_trigger.py |
| 2 | APScheduler cron for daily Scout | d49dfb8 | src/api/main.py, requirements.txt |

## Test Results

- **New tests:** 11 (6 in test_ingest.py, 5 in test_trigger.py)
- **Total suite:** 50 tests, all passing
- **No regressions** in existing scout/trigger tests

## Decisions Made

1. **APScheduler 3.x over Celery/ARQ** — no message broker needed for a single daily cron; AsyncIOScheduler integrates cleanly with FastAPI lifespan
2. **tier="BRIEF" for manual seeds** — user-submitted seeds are always surfaced in briefings; score=0.0 indicates unscored (not low relevance)
3. **Deduplication by source_url** — manual seeds may not have arxiv IDs, so source_url is the natural idempotency key

## Deviations from Plan

None — plan executed exactly as written. TDD flow followed: RED commit (4ff0d6c) then GREEN implementation (df601c3, d49dfb8).

## Self-Check: PASSED

All files present and all commits verified:
- FOUND: src/pipeline/ingest.py
- FOUND: tests/test_ingest.py
- FOUND: src/api/main.py
- FOUND: d49dfb8 (APScheduler cron)
- FOUND: df601c3 (manual seed implementation)
- FOUND: 4ff0d6c (TDD RED tests)
