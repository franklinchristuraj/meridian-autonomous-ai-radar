---
phase: 04-vault-integration
plan: "01"
subsystem: pipeline
tags: [translator, vault, tdd, schema-migration, seed-notes]
dependency_graph:
  requires:
    - src/db/schema.py (confidence migration)
    - src/db/client.py (get_client)
    - weaviate Signals collection (tier=VAULT, confidence property)
  provides:
    - src/pipeline/translator.py (run_translator_pipeline, full translator API)
    - src/db/schema.py (_migrate_signals_confidence)
    - tests/test_translator.py (24 tests)
  affects:
    - Obsidian vault filesystem ($OBSIDIAN_VAULT_PATH/01_seeds/)
    - heartbeat/translator.json
tech_stack:
  added:
    - src/pipeline/translator.py
    - tests/test_translator.py
  patterns:
    - TDD (RED→GREEN→REFACTOR)
    - Idempotent schema migration (same pattern as cluster_id, reasoning)
    - Heartbeat file for pipeline observability
    - Frontmatter YAML regex parse for duplicate detection
key_files:
  created:
    - src/pipeline/translator.py
    - tests/test_translator.py
  modified:
    - src/db/schema.py
decisions:
  - "get_vault_seeds_path called OUTSIDE try/except so misconfiguration raises immediately, not silently"
  - "Confidence filtering done post-query in Python (not Weaviate filter) to handle None values gracefully"
  - "Slug collision handled with -2, -3 suffix loop (simple, no UUID needed)"
  - "arxiv_url extracted from frontmatter via regex (no YAML parser dependency)"
metrics:
  duration_minutes: 15
  completed_date: "2026-03-16"
  tasks_completed: 1
  files_changed: 3
---

# Phase 4 Plan 01: Translator Pipeline Summary

**One-liner:** Translator pipeline with TDD: VAULT signal fetch (confidence >= 0.8), 3-seed daily cap, duplicate detection via frontmatter regex, vault-template-compatible seed note rendering, and confidence NUMBER schema migration.

## What Was Built

The core engine of Phase 4 — `src/pipeline/translator.py` — selects the top 3 high-confidence VAULT signals each pipeline run and deposits them as properly-formatted seed notes into Franklin's Obsidian vault at `$OBSIDIAN_VAULT_PATH/01_seeds/`.

### Functions implemented

| Function | Purpose |
|---|---|
| `get_vault_seeds_path()` | Validates `OBSIDIAN_VAULT_PATH` env var, returns `Path` to `01_seeds/` |
| `fetch_vault_signals(client)` | Queries Weaviate VAULT signals since yesterday, post-filters confidence >= 0.8 |
| `rank_and_cap(signals, max_n=3)` | Sorts descending by confidence, caps at max_n |
| `_load_deposited_urls(seeds_path)` | Globs `*.md`, regex-parses frontmatter, returns set of `arxiv_url` values |
| `slugify_title(title)` | Lowercase alphanumeric slug, edge-dash stripping, "untitled" fallback |
| `render_seed_note(signal)` | Full YAML frontmatter + body matching vault seed template + Meridian extensions |
| `write_translator_heartbeat(deposited)` | Writes `heartbeat/translator.json` |
| `run_translator_pipeline()` | Orchestrator: validate path → fetch → rank → dedup → write → heartbeat |

### Schema migration added

`_migrate_signals_confidence` added to `src/db/schema.py` and called from `init_schema()`. Follows exact pattern of `_migrate_signals_cluster_id` — idempotent, swallows `Exception` on duplicate property.

## Test Coverage

24 tests in `tests/test_translator.py`, all passing:
- Schema migration (idempotency)
- Confidence filtering edge cases (None, 0.5, 0.9)
- Expected key validation on returned dicts
- Ranking sort order and cap enforcement
- Duplicate detection (valid frontmatter, corrupt file, empty dir)
- Seed note frontmatter field completeness
- Slug generation (basic, special chars, edge dashes)
- Vault path environment error handling
- Heartbeat JSON structure
- Pipeline happy path, error swallowing, duplicate skip, daily cap, slug collision

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `src/pipeline/translator.py` exists and contains all 8 exported functions
- [x] `src/db/schema.py` contains `_migrate_signals_confidence` and calls it from `init_schema()`
- [x] `tests/test_translator.py` has 24 tests, all passing
- [x] Full test suite: 110 passed, 0 failed
- [x] Commit 2445916: RED tests
- [x] Commit 841ec85: GREEN implementation

## Self-Check: PASSED
