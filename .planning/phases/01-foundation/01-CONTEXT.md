# Phase 1: Foundation - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy Weaviate schema (signals, patterns, hypotheses, feedback, briefings), bootstrap 15-20 patterns in the pattern library, install and configure Claude Code CLI on VPS as agent runtime, and wire a FastAPI pipeline orchestrator with Make.com webhook trigger. All four deliverables are co-equal — none can be deferred.

</domain>

<decisions>
## Implementation Decisions

### Pattern Library Bootstrap
- **Domains:** Focus on Agentic Systems and LLMOps & Observability — these are Franklin's core expertise areas
- **Count:** 15-20 seed patterns minimum before Scout can score meaningfully
- **Pattern entry format (full framework):** Name + description + keywords + example signals + maturity level (emerging/established/declining) + related patterns + contrarian take
- **Authoring process:** Claude drafts patterns from Franklin's vault knowledge notes (05_knowledge/), Franklin reviews and refines before loading into Weaviate
- **Vault linking:** Bidirectional — each Weaviate pattern references its vault source note path, and vault notes get updated with Weaviate pattern ID

### Make.com Trigger Design
- **Schedule:** Daily cron at 5-6 AM (briefing ready before Franklin wakes up)
- **Additional triggers:** Manual webhook for on-demand runs
- **Make.com scope:** Dumb trigger only — fires HTTP POST to FastAPI endpoint, nothing else. All scheduling logic in Make, all pipeline logic in FastAPI.
- **Authentication:** Shared secret header (X-API-Key with static token) — simple and sufficient for personal single-user system

### Claude's Discretion
- Weaviate collection schema design (property types, indexing strategy, embedding config)
- VPS Claude Code CLI installation and configuration approach
- FastAPI endpoint structure and background task implementation
- Embedding model deployment (nomic-embed-text-v1.5 per research recommendation)
- Weaviate RQ8 quantization configuration

</decisions>

<specifics>
## Specific Ideas

- Pattern entries should mirror Franklin's thinking style — each includes a "contrarian take" field, reflecting how Franklin interprets the pattern differently from consensus
- Patterns are drafted from existing 05_knowledge/ vault notes, not invented from scratch
- Make.com is deliberately kept dumb — Franklin wants pipeline logic centralized in FastAPI, not split across Make scenarios

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, separate repo (~/Projects/meridian)

### Established Patterns
- PWA already live with Next.js + FastAPI — FastAPI patterns from existing PWA may inform the pipeline orchestrator design
- Weaviate running on VPS via Docker — no setup needed for the database itself

### Integration Points
- Make.com → FastAPI: HTTP POST webhook with X-API-Key header
- FastAPI → Claude Code CLI: subprocess invocation via `claude -p`
- Weaviate: Python client v4.20+ (gRPC)
- Obsidian MCP at mcp.ziksaka.com: for vault queries during pattern bootstrap

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-03-13*
