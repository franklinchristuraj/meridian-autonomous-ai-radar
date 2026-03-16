# Forward Intelligence Radar (Meridian)

## What This Is

An autonomous research intelligence system that scans the AI landscape daily, scores signals against a personal pattern library, clusters them into trends, generates a structured morning briefing, and auto-deposits the highest-confidence signals as seed notes into an Obsidian vault. Franklin defines "better" — the agents iterate everything else.

## Core Value

Every morning, a useful briefing surfaces AI signals worth my attention — without me scanning anything manually. The system compresses time-to-take, not replaces thinking.

## Requirements

### Validated

- ✓ Weaviate collections deployed (Signals, Patterns, Hypotheses, Feedback, Briefings) with idempotent schema — v1.0
- ✓ Pattern library bootstrapped with 16 seed patterns across Agentic Systems, LLMOps, RAG — v1.0
- ✓ Claude Code CLI installed and configured on VPS as agent runtime — v1.0
- ✓ FastAPI pipeline orchestrator with Make.com webhook trigger and X-API-Key auth — v1.0
- ✓ Daily ArXiv fetch from 6 AI/ML categories with keyword filtering and deduplication — v1.0
- ✓ LLM relevance scoring (Claude Haiku) against pattern library (1-10 scale with reasoning) — v1.0
- ✓ Semantic source-to-pattern matching via Weaviate nearVector search — v1.0
- ✓ Signal clustering and trend detection (Analyst agent, Claude Sonnet) — v1.0
- ✓ Morning briefing generated: what's happening → time horizon → recommended action — v1.0
- ✓ Auto-deposit VAULT-tier signals as seeds to Obsidian vault with provenance frontmatter — v1.0

### Active

- [ ] Briefing view integrated into existing Next.js + FastAPI PWA
- [ ] Signal feedback mechanism (rate each briefing item) in PWA
- [ ] Feedback-driven scoring calibration — weights auto-adjust based on ratings
- [ ] Source expansion beyond ArXiv (GitHub, HuggingFace, patents, product launches)
- [ ] Hypothesis tracking with confidence scores and evidence linking
- [ ] LLM observability dashboards (Phoenix)
- [ ] Monthly calibration eval with test suite of known-good + known-noise signals

### Out of Scope

- Telegram delivery — briefings go to PWA + Obsidian vault only
- Voice TTS briefing — deferred to future iteration
- Real-time streaming — daily batch processing is sufficient
- Multi-user support — personal system for Franklin only
- Full-text paper processing — abstracts contain sufficient signal for scoring
- Automatic knowledge note editing — human friction on mature notes is the quality gate; seeds only
- Social media ingestion (Twitter/X, Reddit) — high-volume low-signal; hype calibration proxy only

## Context

**Current state:** v1.0 MVP shipped 2026-03-16. ~4,670 lines of Python, 116 tests passing.

**Architecture:**
- **Data backbone:** Weaviate on VPS (Docker) — 5 collections with idempotent schema migrations
- **Agent runtime:** Claude Code CLI on VPS via `invoke_claude()` subprocess wrapper
- **Orchestration:** FastAPI with APScheduler 3.x for daily cron (06:00 UTC), Make.com for external triggers
- **Pipeline chain:** Scout → Analyst → Briefing → Translator (each stage triggers the next)
- **Agent models:** Claude Haiku (Scout scoring — cheap, fast), Claude Sonnet (Analyst clustering + Briefing narrative — deeper reasoning)
- **Vault integration:** Direct filesystem write to `$OBSIDIAN_VAULT_PATH/01_seeds/` — no MCP server, no REST API plugin
- **Auth:** X-API-Key header on all endpoints, shared secret
- **Monitoring:** Heartbeat JSON files per pipeline stage

**Tech stack:**
- Python 3.11, FastAPI, Weaviate Python client v4, APScheduler 3.x, arxiv 2.4.1
- pytest (116 tests), TDD workflow throughout
- VPS deployment, Make.com webhook triggers

**Known technical debt:**
- Schema migrations are idempotent but manual — no migration framework
- Confidence filtering done post-query in Python (not Weaviate filter) to handle None values
- No retry logic on Translator failures — next day's run catches up
- Performance metrics in STATE.md are partially populated

## Constraints

- **Solo operator:** Franklin is the only user and maintainer — architecture must be low-maintenance
- **Time:** ~14-16 hrs/week available outside day job
- **Cost awareness:** LLM token costs for daily scanning need monitoring (Phoenix planned for v2)
- **Pattern bootstrap:** System's value grows with pattern library quality — patterns need curation over time

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Make.com over n8n | Franklin works at Make, native expertise, trigger/webhook layer only | ✓ Good — clean separation of scheduling vs logic |
| Remote Claude Code as agent runtime | Full agent capabilities, not limited to Make scenario logic | ✓ Good — subprocess wrapper enables clean testing |
| Weaviate as single backbone | Handles structured + semantic in one service, already deployed | ✓ Good — nearVector scoring + collection storage in one |
| Three-tier gate (BRIEF/VAULT/ARCHIVE) | Nothing thrown away, but only best items consume attention | ✓ Good — clean separation of attention levels |
| Auto-deposit seeds, never auto-edit knowledge | Human friction on mature notes is the quality gate | ✓ Good — seeds are additive, never destructive |
| Direct filesystem write (not Obsidian MCP) | Simpler, no dependency on MCP server availability | ✓ Good — eliminated external dependency |
| Pattern library co-developed with infrastructure | Running Scout against empty patterns produces misleading calibration | ✓ Good — 16 patterns ready on day one |
| APScheduler for daily cron (not Make.com) | No broker needed, asyncio-native, configurable via env vars | ✓ Good — zero external dependency for scheduling |
| Claude Haiku for scoring, Sonnet for reasoning | Cost optimization — Haiku is 10x cheaper for high-volume scoring | ✓ Good — keeps daily cost low |
| Idempotent schema migrations | No migration framework needed, safe to re-run | ✓ Good — simple and reliable |
| Lazy imports for pipeline chaining | Prevents circular imports, clean test isolation via @patch | ✓ Good — each stage independently testable |
| TDD throughout all phases | Tests written first, then implementation | ✓ Good — 116 tests, zero regressions across 4 phases |
| 25-hour staleness threshold (not 24) | Allows for slight scheduling drift without false stale flags | ✓ Good — practical over pedantic |
| Post-query confidence filtering in Python | Handles None values gracefully, avoids Weaviate filter complexity | ⚠️ Revisit — may need Weaviate-side filtering at scale |

---
*Last updated: 2026-03-16 after v1.0 milestone*
