---
phase: 02-scout-pipeline
plan: "01"
subsystem: pipeline
tags: [arxiv, weaviate, haiku, scoring, keyword-filter, tdd]
dependency_graph:
  requires: [src/db/schema.py, src/db/client.py, src/runtime/claude_runner.py]
  provides: [src/pipeline/scout.py, src/pipeline/__init__.py]
  affects: [src/api/routes/trigger.py]
tech_stack:
  added: [arxiv>=2.4,<3]
  patterns: [unittest.mock.patch, MagicMock, TDD red-green, idempotent schema migration]
key_files:
  created:
    - src/pipeline/__init__.py
    - src/pipeline/scout.py
    - tests/test_scout.py
  modified:
    - src/db/schema.py
    - requirements.txt
decisions:
  - "score_paper uses regex fallback re.search(r'\\{.*\\}', result, re.DOTALL) before raising ValueError for unparseable Haiku responses"
  - "reasoning stored as dedicated TEXT property in Signals via idempotent _migrate_signals_reasoning migration"
  - "run_scout_pipeline stub included in scout.py for Plan 02 wiring (not yet called from trigger.py)"
metrics:
  duration: ~20min
  completed: 2026-03-15
  tasks_completed: 1
  tasks_total: 1
  files_created: 3
  files_modified: 2
---

# Phase 2 Plan 1: Scout Pipeline Helpers Summary

**One-liner:** Scout helper functions implemented TDD-first — ArXiv fetch, keyword pre-filter, Haiku scoring with JSON fallback, tier assignment, and idempotent Signals schema migration for `reasoning` property.

## What Was Built

All Scout pipeline building blocks are now independently importable from `src.pipeline.scout`:

| Function | Purpose |
|----------|---------|
| `build_arxiv_query` | Constructs multi-category + submittedDate query string |
| `fetch_arxiv_papers` | Fetches up to 500 papers via arxiv.Client |
| `normalize_arxiv_id` | Strips URL prefix and version suffix from entry_id |
| `fetch_pattern_keywords` | Pulls live keyword list from Weaviate Patterns collection |
| `keyword_density` | Counts keyword hits in text (case-insensitive) |
| `keyword_filter` | Ranks by density, excludes 0-hits, caps at 50 |
| `get_top_patterns` | near_text query returning top-5 patterns with uuid/distance |
| `score_paper` | Haiku call with structured JSON prompt + regex fallback |
| `assign_tier` | BRIEF>=7.0 / VAULT>=5.0 / ARCHIVE<5.0 |
| `arxiv_id_exists` | Filter query on Signals for dedup check |
| `write_signal` | Idempotent insert (skips existing arxiv_id) |
| `run_scout_pipeline` | Full orchestrator stub (wired in Plan 02) |

Schema migration adds `reasoning` TEXT property to Signals idempotently via `_migrate_signals_reasoning`, called from `init_schema()`.

## Test Coverage

19 unit tests in `tests/test_scout.py` covering:
- Happy path for every helper
- Edge cases: bad JSON (prose-wrapped), unparseable JSON (ValueError), duplicate arxiv_id (insert skipped), zero-hit keyword filter exclusion
- Tier boundaries: 7.0/6.9/5.0/4.9 boundary values

Full suite: 35 passed, 0 regressions.

## Decisions Made

1. **JSON fallback strategy:** `score_paper` tries `json.loads(raw["result"])` first; if that fails, uses `re.search(r'\{.*\}', text, re.DOTALL)` to extract the JSON block; raises `ValueError` if still unparseable. This matches the pitfall documented in RESEARCH.md.

2. **`reasoning` as dedicated TEXT property:** Added via idempotent migration rather than embedding in a `scoring_metadata` blob — keeps the field readable and searchable for Franklin's 5-briefing calibration review.

3. **`run_scout_pipeline` stub in scout.py:** Included so Plan 02 only needs to wire the import in `trigger.py` rather than define the orchestrator from scratch.

## Deviations from Plan

None — plan executed exactly as written. All 16 required test behaviors implemented (19 tests total — 3 additional keyword_density edge cases added under Rule 2 for completeness).

## Self-Check: PASSED

- src/pipeline/scout.py: FOUND
- src/pipeline/__init__.py: FOUND
- tests/test_scout.py: FOUND
- commit 73d2b20: FOUND
