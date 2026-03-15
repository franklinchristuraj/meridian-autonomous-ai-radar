# Phase 4: Vault Integration - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

VAULT-tier signals with confidence >= 0.8 are automatically deposited as seed notes in Franklin's Obsidian vault (`01_seeds/`) by a Translator agent. Max 3 seeds per day, full provenance in frontmatter, no existing notes modified. The Translator extends the daily pipeline chain (Scout → Analyst → Briefing → Translator) and exposes API endpoints for manual triggering and deposit listing.

</domain>

<decisions>
## Implementation Decisions

### Obsidian Delivery Method
- Direct filesystem write to the vault directory on the VPS — no MCP server, no REST API plugin
- Vault path configured via `OBSIDIAN_VAULT_PATH` environment variable
- Fail loud on startup if vault path or `01_seeds/` directory doesn't exist or isn't writable
- At runtime, Translator skips silently if vault becomes unavailable (log error, don't block pipeline)

### Seed Note Structure
- Match existing vault seed template (`00_system/templates/seed_template.md`) for frontmatter convention
- Keep all template fields: `folder`, `type`, `created`, `status` ("raw"), `urgency`, `context` ("work"), `source` ("meridian"), `spark_stage` ("capture"), `tags`, `agent_context`
- Add Meridian-specific fields: `auto_deposit: true`, `signal_uuid`, `confidence`, `score`, `matched_patterns`, `arxiv_url`
- Tags: `[seed, auto-deposit]`
- Filename format: title slug only (e.g., `multi-agent-orchestration-framework.md`) — date lives in frontmatter
- Body: rich context — paper title (H1), full abstract, matched patterns with context, Analyst cluster context, recommended reading path

### Selection & Daily Cap
- Filter: VAULT-tier signals with confidence >= 0.8 (no additional score floor)
- Rank: highest confidence first, take top 3
- Duplicate detection: scan existing `01_seeds/` frontmatter for matching `arxiv_url` before writing — skip if already deposited
- Daily cap enforced per pipeline run (count existing seeds deposited today)

### Pipeline Timing & Error Handling
- Translator runs after Briefing completes — extends the chain: Scout → Analyst → Briefing → Translator
- Translator failure does not affect the pipeline — log error, skip deposit, try again next run
- No retry logic — if it fails, next day's run catches up
- Manual trigger endpoint: `POST /vault/deposit` (same X-API-Key auth pattern)
- Deposit listing endpoint: `GET /vault/deposits` — returns recent deposits (date, title, signal_uuid)

### Claude's Discretion
- Translator agent prompt design and model choice
- Rich context body formatting and section structure
- Slug generation algorithm for filenames
- Exact frontmatter field ordering
- Logging verbosity and format
- `GET /vault/deposits` response pagination or date filtering

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Vault convention
- `~/Documents/franklin-vault/00_system/templates/seed_template.md` — Seed note frontmatter template (MUST match this convention + Meridian extensions)

### Requirements
- `.planning/REQUIREMENTS.md` — DELIV-02 defines acceptance criteria (confidence >= 0.8, max 3/day, #auto-deposit tag, provenance, no existing note modification)

### Pipeline patterns
- `src/pipeline/briefing.py` — Briefing agent pattern (Translator follows same shape: fetch signals → process → write output)
- `src/pipeline/scout.py` — Pipeline orchestration pattern (chain trigger at end of run)
- `src/runtime/claude_runner.py` — `invoke_claude()` wrapper for agent calls

### Schema & data
- `src/db/schema.py` — Signal properties including `tier`, `confidence`, `score`, `matched_pattern_ids`
- `src/db/client.py` — Weaviate client factory

### API patterns
- `src/api/routes/briefing.py` — Route pattern for trigger + read endpoints
- `src/api/auth.py` — X-API-Key auth middleware

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `invoke_claude(prompt, model)` in `src/runtime/claude_runner.py` — Claude CLI wrapper, reuse for Translator agent calls
- `get_client()` in `src/db/client.py` — Weaviate client factory
- Analyst's `fetch_todays_signals()` pattern — query VAULT-tier signals with confidence filter
- Briefing's `_sort_and_cap_items()` — pattern for ranking and capping results

### Established Patterns
- Pipeline function shape: fetch → process → write → chain next stage (from scout.py, briefing.py)
- Schema migration: idempotent `_migrate_signals_*` functions for adding properties
- FastAPI + BackgroundTasks for async pipeline execution
- X-API-Key auth middleware on all trigger endpoints

### Integration Points
- Briefing `run_briefing_pipeline()` end → trigger Translator
- Weaviate Signals collection: query VAULT-tier with confidence >= 0.8
- Filesystem: write to `$OBSIDIAN_VAULT_PATH/01_seeds/`
- FastAPI routes: new `/vault/deposit` trigger + `/vault/deposits` listing
- Register router in `src/api/main.py`

</code_context>

<specifics>
## Specific Ideas

- Rich context body should feel like a research brief — not just raw abstract, but why this signal matters in context of matched patterns and cluster themes
- `agent_context` field should be meaningful: "Auto-deposited VAULT signal from Meridian — [brief reason from Translator agent]"
- Seeds should be immediately useful when Franklin opens them in Obsidian — no additional context gathering needed

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-vault-integration*
*Context gathered: 2026-03-15*
