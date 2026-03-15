# Phase 3: Intelligence + Briefing - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Scored signals from the Scout pipeline are clustered into trends by an Analyst agent, mapped to patterns, and assembled into a structured morning briefing by a Briefing agent. The briefing is stored in Weaviate and served via API endpoints that the existing PWA consumes to display at `/briefing/today`. This phase delivers end-to-end: backend agents + API + PWA route.

</domain>

<decisions>
## Implementation Decisions

### Clustering Approach
- Hybrid: pattern-anchored clustering first (group by shared matched_pattern_ids), then semantic similarity clustering for signals that don't anchor to a pattern
- Target 5-8 clusters per day — enough nuance without noise
- Write cluster_id back to individual Signal objects in Weaviate (no separate Clusters collection)
- Singletons (signals that don't cluster well) appear in the briefing as "Notable singles" section — still worth seeing

### Analyst Agent Design
- Analyst receives full context per signal: title + abstract + score + matched patterns
- Analyst outputs structured JSON with cluster assignments AND 1-2 sentence theme summary per cluster
- Uses Sonnet (claude-sonnet-4-5) via invoke_claude()
- Clusters today's signals only, but queries last 7 days to annotate trends ("3rd paper on X this week")

### Briefing Narrative Design
- Top 10 items per briefing (all BRIEF-tier clusters + notable singles, fill with top VAULT items)
- Strategic advisor tone — opinionated, forward-looking ("This cluster suggests the industry is moving toward X — watch for Y")
- Opens with 3-sentence executive summary (landscape pulse: what's hot, surprises, volume)
- Per-item structure: what's happening → time horizon → recommended action
- Action type is tier-based: BRIEF items get strategic actions ("Consider updating pattern X"), VAULT items get read/investigate actions ("Read the full paper")
- Single Sonnet call generates the full narrative (executive summary + all items) from Analyst output

### Pipeline Orchestration
- Separate pipeline from Scout — Analyst+Briefing runs as its own function triggered after Scout completion
- Scout calls `run_analyst_briefing_pipeline()` at end of successful run
- Manual trigger endpoint: POST /briefing/generate (re-run briefing without re-running Scout)
- If Analyst clustering fails, pipeline fails entirely — no degraded briefing. Staleness warning in PWA signals the problem
- Same auth pattern as Scout trigger (X-API-Key)

### PWA Briefing Viewer
- Code lives in the existing PWA repo (Next.js + FastAPI), not in this meridian repo
- Meridian serves two API endpoints:
  - `/briefing/today/narrative` — pre-rendered narrative text (executive summary + items)
  - `/briefing/today/data` — structured JSON (clusters, signals, scores, patterns)
- Staleness warning: amber banner at top of briefing if pipeline hasn't run in >25 hours ("Last updated 28h ago — pipeline may have failed"). Non-blocking — briefing still visible below.
- Briefing history: /briefing/today with a sidebar/list showing last 7 briefings. Past briefings accessible via /briefing/{date}
- Full stack delivery in this phase (backend agents + API + PWA route)

### Claude's Discretion
- Exact Analyst prompt wording and clustering instructions
- Briefing narrative formatting (markdown vs HTML vs plain text in items_json)
- Semantic clustering algorithm choice (Weaviate near_text vs custom embeddings)
- PWA component design, styling, and layout details
- API response pagination or caching strategy
- Error logging and monitoring approach for the Analyst+Briefing pipeline

</decisions>

<specifics>
## Specific Ideas

- "Strategic advisor tone" — like a trusted advisor giving a read on the landscape, not a dry news aggregator
- "Landscape pulse" opener — 3 sentences that tell Franklin what kind of day it is before diving into items
- Trend annotations: "This is the 3rd paper on multi-agent orchestration this week" — connect today's signals to recent momentum
- Tiered actions create a natural reading flow: high-signal items (BRIEF) get strategic framing, lower items (VAULT) get investigation pointers

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `invoke_claude(prompt, model)` in `src/runtime/claude_runner.py` — Claude CLI wrapper with model parameter, used for Haiku scoring, reusable for Sonnet Analyst/Briefing calls
- `get_top_patterns()` in `src/pipeline/scout.py` — Weaviate near_text pattern matching, reusable for pattern-anchored clustering
- `get_client()` in `src/db/client.py` — Weaviate client factory
- Briefings collection already exists in schema with: date, summary, generated_at, item_count, items_json

### Established Patterns
- Pipeline function pattern: `run_scout_pipeline()` in `src/pipeline/scout.py` — fetch → process → write → heartbeat. Analyst+Briefing pipeline should follow same shape
- Schema migration pattern: idempotent `_migrate_signals_*` functions for adding properties. Use same pattern for adding cluster_id to Signals
- FastAPI + BackgroundTasks for async pipeline execution (from trigger.py)
- X-API-Key auth middleware (from auth.py)

### Integration Points
- Scout `run_scout_pipeline()` end → trigger Analyst+Briefing pipeline
- Weaviate Signals collection: read BRIEF+VAULT signals, write cluster_id back
- Weaviate Briefings collection: write generated briefing narrative + structured items
- FastAPI routes: new `/briefing/generate` trigger + `/briefing/today/*` read endpoints
- PWA (separate repo): consumes Meridian's `/briefing/` API endpoints

</code_context>

<deferred>
## Deferred Ideas

- Briefing feedback mechanism (signal rating from PWA) — separate phase
- Pattern momentum tracking (accelerating/decelerating patterns over time) — could enhance executive summary in future
- Briefing delivery via other channels (email, Slack, Telegram) — out of scope

</deferred>

---

*Phase: 03-intelligence-briefing*
*Context gathered: 2026-03-15*
