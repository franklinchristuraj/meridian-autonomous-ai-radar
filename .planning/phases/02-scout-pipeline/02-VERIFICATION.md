---
phase: 02-scout-pipeline
verified: 2026-03-15T17:00:00Z
status: human_needed
score: 17/17 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 16/17
  gaps_closed:
    - "Scout runs daily via cron (APScheduler AsyncIOScheduler in FastAPI lifespan at 06:00 UTC)"
    - "Trigger endpoint repurposed to accept manual seed payloads (SeedPayload Pydantic model)"
    - "Two flows are fully independent: manual seeds via HTTP, daily ArXiv via cron"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Trigger POST /pipeline/trigger with valid API key and JSON body {title, url} and confirm 202 response"
    expected: "HTTP 202 Accepted returned, ingest_manual_seed enqueued as background task"
    why_human: "Live FastAPI endpoint behavior requires a running server to confirm end-to-end"
  - test: "Run pipeline once and verify heartbeat/scout.json is written"
    expected: "heartbeat/scout.json created with last_run, papers_fetched, papers_scored, status=ok"
    why_human: "File is runtime-generated — directory does not exist until write_heartbeat runs"
  - test: "Confirm APScheduler cron fires run_scout_pipeline at 06:00 UTC after server starts"
    expected: "Scout pipeline runs at scheduled time; heartbeat updates; signals appear in Weaviate"
    why_human: "Time-based scheduler behavior cannot be verified statically"
  - test: "Confirm Make.com can POST to /pipeline/trigger with a seed payload and receive 202"
    expected: "Make.com HTTP module returns 202; Signal written to Weaviate with status=manual, tier=BRIEF"
    why_human: "External service integration — cannot verify programmatically from codebase alone"
---

# Phase 2: Scout Pipeline Verification Report (Re-verification)

**Phase Goal:** Build the Scout pipeline — daily-triggered flow that discovers, enriches, and scores competitor signals
**Verified:** 2026-03-15T17:00:00Z
**Status:** human_needed (all automated checks passed; 4 items require live testing)
**Re-verification:** Yes — after gap closure (02-03-PLAN.md closed GAP-01)

---

## Re-verification Summary

Previous verification (2026-03-15T16:10:00Z) found 1 gap: GAP-01 — the trigger endpoint called `run_scout_pipeline` directly, conflating daily ArXiv ingestion with manual seed submission. Plan 02-03 closed this gap by separating the two flows. All 3 must-have truths from the gap closure plan are now verified.

---

## Goal Achievement

### Observable Truths (All 17)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | fetch_arxiv_papers returns list of arxiv Results for a given date | VERIFIED | `def fetch_arxiv_papers` at scout.py:68; arxiv>=2.4,<3 in requirements.txt |
| 2 | keyword_filter returns at most 50 papers ranked by keyword density | VERIFIED | `def keyword_filter` at scout.py:113; tests test_keyword_filter_cap and test_keyword_filter_excludes_zero_hits |
| 3 | get_top_patterns returns top 5 patterns via near_text Weaviate search | VERIFIED | `near_text` call at scout.py:140 |
| 4 | score_paper calls Haiku with paper + 5 patterns and parses structured JSON | VERIFIED | `invoke_claude(prompt, model="claude-haiku-4-5")` at scout.py:178 |
| 5 | score_paper handles malformed Haiku JSON via regex fallback | VERIFIED | test_score_paper_bad_json and test_score_paper_unparseable pass |
| 6 | arxiv_id is normalized to strip URL prefix and version suffix | VERIFIED | `def normalize_arxiv_id` at scout.py:85 |
| 7 | write_signal skips papers whose arxiv_id already exists in Weaviate | VERIFIED | `Filter.by_property("arxiv_id")` at scout.py:225 |
| 8 | Tier assignment: >=7.0 BRIEF, >=5.0 VAULT, <5.0 ARCHIVE | VERIFIED | `def assign_tier` at scout.py:203 |
| 9 | Signals schema includes reasoning TEXT property | VERIFIED | `_migrate_signals_reasoning` at schema.py:37 |
| 10 | run_scout_pipeline orchestrates fetch -> keyword_filter -> score -> write | VERIFIED | `def run_scout_pipeline` at scout.py:261 |
| 11 | Pipeline skips duplicate arxiv_ids before scoring | VERIFIED | test_run_scout_pipeline_skips_duplicates |
| 12 | Failed Haiku calls log error and skip paper without crashing pipeline | VERIFIED | test_run_scout_pipeline_score_failure_continues |
| 13 | Weaviate client is always closed in a finally block | VERIFIED | `finally: client.close()` at scout.py:300-301 |
| 14 | Heartbeat JSON written on successful completion | VERIFIED | `write_heartbeat(len(papers), scored)` at scout.py:298 |
| 15 | Heartbeat is NOT written if pipeline crashes before completion | VERIFIED | test_run_scout_pipeline_no_heartbeat_on_crash |
| 16 | POST /pipeline/trigger accepts manual seed payload and ingests Signal | VERIFIED | SeedPayload model at trigger.py:16; `ingest_manual_seed` called in BackgroundTasks at trigger.py:30; test_trigger_accepts_seed_payload at test_trigger.py:19 |
| 17 | Scout runs daily via APScheduler cron; trigger endpoint handles manual seeds only | VERIFIED | AsyncIOScheduler with run_scout_pipeline at main.py:6,11,15,21-24; trigger.py imports ingest_manual_seed only (no run_scout_pipeline reference) |

**Score:** 17/17 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/pipeline/__init__.py` | Module init | VERIFIED | File exists |
| `src/pipeline/scout.py` | All Scout helper functions | VERIFIED | Substantive implementation; 13 functions present |
| `src/pipeline/ingest.py` | Manual seed ingestion | VERIFIED | 61 lines; `ingest_manual_seed` with dedup by source_url, status=manual, tier=BRIEF |
| `src/api/routes/trigger.py` | Repurposed trigger with SeedPayload | VERIFIED | SeedPayload Pydantic model; calls ingest_manual_seed in BackgroundTasks; no run_scout_pipeline reference |
| `src/api/main.py` | APScheduler lifespan integration | VERIFIED | AsyncIOScheduler; SCOUT_CRON_HOUR/MINUTE env vars; scheduler.start() in lifespan |
| `src/db/schema.py` | Signals collection with reasoning property | VERIFIED | `_migrate_signals_reasoning` confirmed |
| `tests/test_scout.py` | Unit tests for Scout helpers | VERIFIED | 26 test functions |
| `tests/test_ingest.py` | Unit tests for manual seed ingestion | VERIFIED | 165 lines; 6 test functions covering defaults, notes, dedup, client lifecycle |
| `tests/test_trigger.py` | Updated trigger tests with payload validation | VERIFIED | 70 lines; test_trigger_accepts_seed_payload, test_trigger_missing_title_returns_422, auth tests |
| `heartbeat/scout.json` | Written at runtime | RUNTIME | Created by write_heartbeat at runtime; mkdir(parents=True, exist_ok=True) confirmed |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| src/pipeline/scout.py | src/runtime/claude_runner.py | invoke_claude(model='claude-haiku-4-5') | VERIFIED | scout.py:178 |
| src/pipeline/scout.py | src/db/client.py | get_client() | VERIFIED | scout.py:17, called at scout.py:264 |
| src/pipeline/scout.py | Weaviate Patterns collection | near_text query | VERIFIED | scout.py:140 |
| src/pipeline/scout.py | Weaviate Signals collection | filter + insert for dedup write | VERIFIED | scout.py:225 |
| src/api/routes/trigger.py | src/pipeline/ingest.py | import ingest_manual_seed | VERIFIED | trigger.py:9 |
| src/api/main.py | src/pipeline/scout.py | APScheduler cron calling run_scout_pipeline | VERIFIED | main.py:11,24 |
| src/pipeline/ingest.py | Weaviate Signals collection | Filter.by_property("source_url") dedup + insert | VERIFIED | ingest.py:9,38,40,50-53 |
| src/pipeline/scout.py | heartbeat/scout.json | write_heartbeat at end of successful run | VERIFIED | scout.py:298 |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INGEST-01 | 02-01, 02-02, 02-03 | Daily ArXiv fetch from 6 categories via arxiv 2.4.x | SATISFIED | fetch_arxiv_papers; now cron-scheduled via APScheduler at 06:00 UTC |
| INGEST-02 | 02-01, 02-02, 02-03 | LLM relevance scoring (Claude Haiku) against pattern library (1-10 scale) | SATISFIED | score_paper calls invoke_claude with model="claude-haiku-4-5" |
| INTEL-01 | 02-01, 02-02, 02-03 | Semantic source-to-pattern matching via Weaviate nearVector search | SATISFIED | get_top_patterns uses near_text on Patterns collection |

All 3 required requirement IDs satisfied. No orphaned requirements detected.

---

### Anti-Patterns Found

None. No TODO/FIXME/PLACEHOLDER comments, no empty returns, no stub implementations found in any gap-closure files.

---

### Human Verification Required

#### 1. FastAPI Trigger Endpoint Live Test (Manual Seed)

**Test:** Start the server and POST to `/pipeline/trigger` with a valid API key and body `{"title": "Test Paper", "url": "https://example.com"}`.
**Expected:** HTTP 202 Accepted; `ingest_manual_seed` enqueued as background task; Signal written to Weaviate with `status=manual`, `tier=BRIEF`.
**Why human:** Requires a running server with live Weaviate connection; automated tests mock the pipeline.

#### 2. Heartbeat File Written After Real Pipeline Run

**Test:** Start the server and wait for the APScheduler cron to fire (or set SCOUT_CRON_HOUR/MINUTE to trigger immediately), then check `heartbeat/scout.json`.
**Expected:** File created with `last_run`, `papers_fetched`, `papers_scored`, `status: "ok"`.
**Why human:** Runtime-generated file; `heartbeat/` directory does not exist pre-run.

#### 3. APScheduler Cron Fires at Configured Time

**Test:** Start server, wait for 06:00 UTC (or set env vars to a near-future time), confirm `run_scout_pipeline` executes.
**Expected:** Scout pipeline runs at scheduled time; heartbeat updates; signals appear in Weaviate.
**Why human:** Time-based scheduler behavior cannot be verified statically.

#### 4. Make.com Daily Trigger Integration

**Test:** Configure Make.com HTTP module to POST to `/pipeline/trigger` with API key and a seed payload. Confirm 202 response and Signal written.
**Expected:** Make.com returns 202; Signal appears in Weaviate with `status=manual`.
**Why human:** External service integration — cannot verify programmatically.

---

### Gaps Summary

No gaps remain. GAP-01 (trigger/scheduling misalignment) was fully closed by plan 02-03:
- `src/pipeline/ingest.py` created with `ingest_manual_seed` (dedup by source_url, status=manual, tier=BRIEF)
- `src/api/routes/trigger.py` rewritten to accept `SeedPayload` and call `ingest_manual_seed`
- `src/api/main.py` updated with APScheduler `AsyncIOScheduler` scheduling `run_scout_pipeline` daily at 06:00 UTC
- 11 new tests added (165-line test_ingest.py + updated test_trigger.py); total suite: 50 tests, all passing

Phase 02 goal is fully achieved at the code level. 4 items require live environment confirmation.

---

_Verified: 2026-03-15T17:00:00Z_
_Verifier: Claude (gsd-verifier)_
