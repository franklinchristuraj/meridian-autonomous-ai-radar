# Phase 5: LLM Observability - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Phoenix dashboards for token cost monitoring, latency tracking, and pipeline performance visibility. Instrument the full daily pipeline (Scout → Analyst → Briefing → Translator) to send OpenTelemetry traces to the existing Phoenix instance. No new UI in the PWA — Phoenix's built-in web UI handles all visualization.

</domain>

<decisions>
## Implementation Decisions

### Instrumentation scope
- Instrument the full pipeline end-to-end, not just LLM calls
- Covers: ArXiv fetch, Weaviate queries, LLM calls (invoke_claude), file writes, heartbeat writes
- Each daily pipeline run = one trace with child spans per stage (Scout, Analyst, Briefing, Translator)
- Existing heartbeat JSON files kept alongside Phoenix as lightweight health checks — no breaking changes

### Span metadata
- Token counts (input/output) and cost_usd per LLM call — already returned by invoke_claude()
- Model identity (haiku vs sonnet) — for cost attribution
- Input/output payloads — full prompts and responses stored for debugging
- Item counts — papers fetched, signals scored, clusters found, seeds deposited (business metrics per span)

### Dashboard & visualization
- Phoenix UI only — no custom dashboard in the Meridian PWA
- Phoenix already running as separate Docker container on VPS
- Primary metric: signal quality (papers → signals → clusters → seeds funnel)
- Token cost and latency tracked but secondary to signal quality
- Full drill-down into individual LLM prompts/responses enabled for debugging scoring/clustering issues

### Claude's Discretion
- OpenTelemetry SDK configuration details
- Span naming conventions
- Phoenix collector endpoint configuration
- How to structure the trace context passing between pipeline stages
- Data retention / trace cleanup policy

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pipeline architecture
- `src/runtime/claude_runner.py` — invoke_claude() wrapper that returns usage/cost/model data
- `src/pipeline/scout.py` — Scout stage with heartbeat, ArXiv fetch, LLM scoring
- `src/pipeline/analyst.py` — Analyst stage with LLM clustering
- `src/pipeline/briefing.py` — Briefing stage with LLM narrative generation
- `src/pipeline/translator.py` — Translator stage with vault deposit and heartbeat

### Existing monitoring
- `src/api/routes/briefing.py` — Heartbeat staleness check (25-hour threshold)
- `heartbeat/*.json` — Per-stage heartbeat files (scout, briefing, translator)

### Project context
- `.planning/PROJECT.md` — Architecture overview, tech stack, key decisions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `invoke_claude()` in `src/runtime/claude_runner.py`: Already returns `usage`, `cost_usd`, `model` — span metadata available without API changes
- Heartbeat writers in each pipeline module: Show the pattern for post-stage side effects

### Established Patterns
- Pipeline chain: Scout → Analyst → Briefing → Translator, each stage triggers the next via lazy imports
- Subprocess wrapper for Claude CLI — traces need to wrap the `subprocess.run()` call
- APScheduler triggers daily run at 06:00 UTC — trace should start at pipeline entry point
- FastAPI with Make.com webhook trigger — alternative entry point also needs tracing

### Integration Points
- `invoke_claude()` is the single LLM call point — primary instrumentation target
- Pipeline entry in `src/api/routes/` or scheduler — trace root span starts here
- Weaviate client calls in scout.py and analyst.py — need span wrapping
- ArXiv fetch in `src/pipeline/ingest.py` or scout.py — network call span

</code_context>

<specifics>
## Specific Ideas

- Phoenix is already deployed as a Docker container on VPS — no new infrastructure needed, just send traces to it
- Signal quality funnel (papers → signals → clusters → seeds) is the primary dashboard view — not cost

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-llm-observability*
*Context gathered: 2026-03-16*
