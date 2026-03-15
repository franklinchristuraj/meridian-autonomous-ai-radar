---
phase: 02-scout-pipeline
verified: 2026-03-15T16:10:00Z
status: gaps_found
score: 16/17 must-haves verified
re_verification: false
human_verification:
  - test: "Trigger POST /pipeline/trigger with valid API key and confirm 202 response"
    expected: "HTTP 202 Accepted returned, run_scout_pipeline enqueued as background task"
    why_human: "Live FastAPI endpoint behavior requires a running server to confirm end-to-end"
  - test: "Run pipeline once and verify heartbeat/scout.json is written"
    expected: "heartbeat/scout.json created with last_run, papers_fetched, papers_scored, status=ok"
    why_human: "File is runtime-generated — cannot verify pre-execution; directory does not exist yet (created by write_heartbeat on first run)"
  - test: "Confirm Make.com trigger can reach POST /pipeline/trigger"
    expected: "Make.com HTTP module returns 202 and pipeline runs in background"
    why_human: "External service integration — cannot verify programmatically"
---

# Phase 2: Scout Pipeline Verification Report

**Phase Goal:** Implement the Scout pipeline — fetch arXiv papers, parse metadata, score relevance via LLM, and store enriched signals with reasoning.
**Verified:** 2026-03-15T16:10:00Z
**Status:** human_needed (all automated checks passed; 3 items require live testing)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | fetch_arxiv_papers returns list of arxiv Results for a given date | VERIFIED | `def fetch_arxiv_papers(target_date: date | None = None)` at scout.py:68; arxiv>=2.4,<3 in requirements.txt |
| 2 | keyword_filter returns at most 50 papers ranked by keyword density, excluding 0-hit papers | VERIFIED | `def keyword_filter` at scout.py:113; tests test_keyword_filter_cap and test_keyword_filter_excludes_zero_hits |
| 3 | get_top_patterns returns top 5 patterns via near_text Weaviate search | VERIFIED | `near_text` call at scout.py:140; `def get_top_patterns` at scout.py:128 |
| 4 | score_paper calls Haiku with paper + 5 patterns and parses structured JSON response | VERIFIED | `invoke_claude(prompt, model="claude-haiku-4-5")` at scout.py:178 |
| 5 | score_paper handles malformed Haiku JSON via regex fallback | VERIFIED | test_score_paper_bad_json and test_score_paper_unparseable pass; regex fallback decision documented in SUMMARY |
| 6 | arxiv_id is normalized to strip URL prefix and version suffix | VERIFIED | `def normalize_arxiv_id` at scout.py:85; tests test_normalize_arxiv_id_with_version and test_normalize_arxiv_id_no_version |
| 7 | write_signal skips papers whose arxiv_id already exists in Weaviate | VERIFIED | `Filter.by_property("arxiv_id")` at scout.py:225; test_write_signal_duplicate confirms insert NOT called |
| 8 | Tier assignment: >=7.0 BRIEF, >=5.0 VAULT, <5.0 ARCHIVE | VERIFIED | `def assign_tier` at scout.py:203; test_assign_tier covers all boundary values |
| 9 | Signals schema includes reasoning TEXT property | VERIFIED | `_migrate_signals_reasoning` at schema.py:37; idempotent migration called from init_schema() |
| 10 | run_scout_pipeline orchestrates fetch -> keyword_filter -> score -> write in sequence | VERIFIED | `def run_scout_pipeline` at scout.py:261; test_run_scout_pipeline_happy_path verifies call order |
| 11 | Pipeline skips duplicate arxiv_ids before scoring (no wasted Haiku calls) | VERIFIED | test_run_scout_pipeline_skips_duplicates confirms score_paper not called for duplicates |
| 12 | Failed Haiku calls log error and skip paper without crashing pipeline | VERIFIED | test_run_scout_pipeline_score_failure_continues confirms pipeline continues and heartbeat still written |
| 13 | Weaviate client is always closed in a finally block | VERIFIED | `finally: client.close()` at scout.py:300-301; test_run_scout_pipeline_client_closed_on_error |
| 14 | Heartbeat JSON written on successful completion with paper_count and scored_count | VERIFIED | `write_heartbeat(len(papers), scored)` at scout.py:298; test_write_heartbeat confirms JSON keys |
| 15 | Heartbeat is NOT written if pipeline crashes before completion | VERIFIED | test_run_scout_pipeline_no_heartbeat_on_crash confirms write_heartbeat not called on fetch error |
| 16 | trigger.py imports run_scout_pipeline from src.pipeline.scout | VERIFIED | `from src.pipeline.scout import run_scout_pipeline` at trigger.py:8 |
| 17 | Scout runs daily via cron; trigger endpoint accepts manual seeds from user | GAP | Trigger endpoint currently wires to run_scout_pipeline instead of handling manual seeds/articles. Scout should run on cron, not via Make.com trigger. Architectural misalignment. |

**Score:** 16/17 automated truths verified (1 GAP — architectural misalignment)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/pipeline/__init__.py` | Module init | VERIFIED | File exists |
| `src/pipeline/scout.py` | All Scout helper functions | VERIFIED | All 13 functions present; 541-line substantive implementation |
| `tests/test_scout.py` | Unit tests for all Scout helpers (min 100 lines) | VERIFIED | 541 lines, 26 test functions covering all behaviors |
| `src/db/schema.py` | Signals collection with reasoning property | VERIFIED | `reasoning` TEXT property added via idempotent migration |
| `src/api/routes/trigger.py` | Wired trigger calling real scout pipeline | VERIFIED | Real import confirmed, stub removed |
| `heartbeat/scout.json` | Written at runtime on successful pipeline execution | RUNTIME | Directory created by write_heartbeat at runtime; `mkdir(parents=True, exist_ok=True)` confirmed |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| src/pipeline/scout.py | src/runtime/claude_runner.py | invoke_claude(prompt, model='claude-haiku-4-5') | VERIFIED | scout.py:178 matches pattern `invoke_claude.*haiku` |
| src/pipeline/scout.py | src/db/client.py | get_client() for Weaviate operations | VERIFIED | `from src.db.client import get_client` at scout.py:17; called at scout.py:264 |
| src/pipeline/scout.py | Weaviate Patterns collection | near_text query for pattern matching | VERIFIED | `patterns.query.near_text(...)` at scout.py:140 |
| src/pipeline/scout.py | Weaviate Signals collection | filter + insert for dedup write | VERIFIED | `Filter.by_property("arxiv_id").equal(arxiv_id)` at scout.py:225 |
| src/api/routes/trigger.py | src/pipeline/scout.py | import run_scout_pipeline | VERIFIED | `from src.pipeline.scout import run_scout_pipeline` at trigger.py:8 |
| src/pipeline/scout.py | heartbeat/scout.json | write_heartbeat at end of successful run | VERIFIED | `write_heartbeat(len(papers), scored)` at scout.py:298; dir created at runtime |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INGEST-01 | 02-01, 02-02 | Daily ArXiv fetch from 6 categories via arxiv 2.4.x | SATISFIED | fetch_arxiv_papers uses arxiv.Client with 6-category query; arxiv>=2.4,<3 in requirements.txt |
| INGEST-02 | 02-01, 02-02 | LLM relevance scoring (Claude Haiku) against pattern library (1-10 scale) | SATISFIED | score_paper calls invoke_claude with model="claude-haiku-4-5"; score parsed from JSON response |
| INTEL-01 | 02-01, 02-02 | Semantic source-to-pattern matching via Weaviate nearVector search | SATISFIED | get_top_patterns uses near_text on Patterns collection; top-5 patterns with uuid+distance returned |

All 3 required requirement IDs satisfied. No orphaned requirements detected.

---

### Anti-Patterns Found

None. No TODO/FIXME/PLACEHOLDER comments, no empty returns, no stub implementations found in src/pipeline/scout.py.

---

### Human Verification Required

#### 1. FastAPI Trigger Endpoint Live Test

**Test:** Start the server and POST to `/pipeline/trigger` with a valid API key header.
**Expected:** HTTP 202 Accepted; background task enqueued; no crash on import.
**Why human:** Requires a running server; automated tests mock the pipeline and don't exercise the real FastAPI startup path.

#### 2. Heartbeat File Written After Real Pipeline Run

**Test:** Trigger a real pipeline run (or call `run_scout_pipeline()` directly with a live Weaviate connection) and check that `heartbeat/scout.json` exists with correct JSON keys.
**Expected:** File created at `heartbeat/scout.json` with `last_run`, `papers_fetched`, `papers_scored`, `status: "ok"`.
**Why human:** The `heartbeat/` directory does not exist pre-run; it is created at runtime. Cannot verify a runtime-generated file statically.

#### 3. Make.com Daily Trigger Integration

**Test:** Confirm Make.com scenario is configured to POST to the correct endpoint URL with API key, and that a scheduled run completes without error.
**Expected:** Make.com returns 202; pipeline runs; heartbeat updates; signals appear in Weaviate.
**Why human:** External service integration — cannot verify programmatically from codebase alone.

---

### Gaps Summary

#### GAP-01: Trigger endpoint / scheduling misalignment

**Issue:** `/pipeline/trigger` currently calls `run_scout_pipeline` directly. The intended architecture is:
- **Scout pipeline** runs on a **cron schedule** (daily, no external trigger needed)
- **Trigger endpoint** receives **manual seeds, articles, and insights** from the user via Make.com

**Impact:** The endpoint serves the wrong purpose. Users cannot send manual inputs, and the Scout pipeline has no cron-based scheduling.

**Fix required:**
1. Repurpose `/pipeline/trigger` to accept manual seed payloads (articles, URLs, notes) and ingest them as Signals
2. Add cron scheduling for `run_scout_pipeline` (system cron or APScheduler)
3. Update tests to reflect the two distinct flows

---

_Verified: 2026-03-15T16:10:00Z_
_Verifier: Claude (gsd-verifier)_
