# Phase 2: Scout Pipeline - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Daily ArXiv ingestion from 6 AI/ML categories, keyword-filtered against the pattern library, scored by Claude Haiku with nearVector pattern matching, routed through the three-tier gate (BRIEF/VAULT/ARCHIVE), and written to the Signals collection in Weaviate. The Scout runs autonomously via Make.com trigger → FastAPI → background task. Phase 3 (clustering + briefing generation) is out of scope.

</domain>

<decisions>
## Implementation Decisions

### ArXiv Fetching Scope
- Fetch papers from cs.AI, cs.CL, cs.CV, cs.LG, cs.MA, cs.SD — previous day only (24-hour window)
- If a run is missed, next run catches the gap naturally (ArXiv API supports date range queries)
- Keyword pre-filtering before any Haiku calls: match paper title + abstract against pattern library keywords
- Keywords sourced dynamically from the Patterns collection in Weaviate (no static list)
- As patterns are added/updated, the keyword filter auto-expands
- Soft cap of ~50 papers per day after keyword filtering — rank by keyword density, take top 50
- Deduplication by arxiv_id before writing to Weaviate

### Scoring Prompt Design
- Pattern selection per paper: embed title+abstract, run nearVector against Patterns collection, take top 5 closest matches
- Individual Haiku calls — one paper + its top-5 patterns per call (not batched)
- Haiku returns structured output: relevance score (1-10), matched pattern names, and 1-2 sentence reasoning
- Relevance framing: pattern alignment + novelty — high score means the paper directly advances or challenges an existing pattern with novel evidence/approach; low score means tangentially related or rehashes known work
- Pattern contrarian_take fields inform the scoring prompt to help calibrate novelty detection
- Reasoning is stored alongside the score to aid Franklin's calibration during the 5-briefing validation gate

### Tier Thresholds & Routing
- BRIEF >= 7.0 / VAULT 5.0-6.9 / ARCHIVE < 5.0 (from requirements — not discussed, using defaults)
- Tier assignment written to Signal.tier field; matched pattern IDs written to Signal.matched_pattern_ids

### Claude's Discretion
- Exact scoring prompt wording and JSON schema for Haiku output
- ArXiv API client implementation (arxiv 2.4.1 library per requirements)
- Heartbeat file format and location
- Error handling and retry strategy for Haiku calls and ArXiv API
- How reasoning text is stored (new Signal property or embedded in existing field)
- Keyword density ranking algorithm for the soft cap

</decisions>

<specifics>
## Specific Ideas

- Pattern contrarian_take should be part of the scoring context — it represents Franklin's differentiated perspective and helps Haiku distinguish genuinely novel work from consensus-confirming noise
- The 5-briefing validation gate (Phase 2 success criterion #4) means scoring reasoning must be human-readable — Franklin needs to understand WHY papers scored high/low to calibrate
- Keep Haiku calls cheap: individual calls with focused 5-pattern context, not full pattern library dumps

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/runtime/claude_runner.py`: `invoke_claude()` wrapper — subprocess call to Claude CLI with JSON output. Currently defaults to Sonnet; Scout will call with `model="claude-haiku-4-5"`
- `src/db/schema.py`: Signals collection already has score, tier, status, arxiv_id, matched_pattern_ids fields — ready for Scout writes
- `src/db/client.py`: `get_client()` returns connected Weaviate client with env-configured host/ports
- `src/api/routes/trigger.py`: `run_scout_pipeline()` stub — this is the entry point to implement
- `patterns/seed/*.json`: 16 seed patterns with keywords, maturity, contrarian_take, example_signals — loaded in Weaviate Patterns collection

### Established Patterns
- FastAPI BackgroundTasks for async pipeline execution (trigger.py)
- Weaviate Python client v4 with gRPC connection
- Idempotent collection creation (schema.py checks `.exists()` before creating)
- Pattern idempotency via name-match lookup before insert

### Integration Points
- Make.com → FastAPI POST `/pipeline/trigger` with X-API-Key auth → BackgroundTasks → `run_scout_pipeline()`
- Weaviate Patterns collection: nearVector search for pattern matching
- Weaviate Signals collection: write scored papers with tier routing
- `invoke_claude()`: needs model parameter override for Haiku

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-scout-pipeline*
*Context gathered: 2026-03-15*
