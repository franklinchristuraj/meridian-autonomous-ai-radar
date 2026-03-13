# Forward Intelligence Radar (Meridian)

## What This Is

An autonomous research intelligence system that scans the AI landscape daily, connects signals to a personal pattern library, and delivers a strategic briefing via a personal PWA. Franklin is the client of this intelligence team, not the operator — he defines "better," the agents iterate everything else.

## Core Value

Every morning, a useful briefing surfaces AI signals worth my attention — without me scanning anything manually. The system compresses time-to-take, not replaces thinking.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Weaviate collections designed and deployed (signals, patterns, hypotheses, feedback)
- [ ] ArXiv Scout agent: daily fetch, embed, score against pattern library
- [ ] Three-tier gate: BRIEF (≥7.0) / VAULT (5.0-6.9) / ARCHIVE (<5.0)
- [ ] Pattern library bootstrapped with initial entries in Weaviate
- [ ] Analyst agent: cluster signals, map to patterns, propose new pattern candidates
- [ ] Feedback mechanism for daily signal rating (design TBD — PWA or vault)
- [ ] PAR tracking operational
- [ ] Translator agent: connect signals to vault knowledge, auto-deposit seeds
- [ ] Hypothesis tracking: seed initial hypotheses, link signals, track confidence
- [ ] Morning Briefing generator: curate top items, format with recommendations
- [ ] Briefing + feedback UI integrated into existing PWA (Next.js + FastAPI)
- [ ] Scoring weights auto-adjust based on feedback patterns
- [ ] Source expansion beyond ArXiv (patents, GitHub, HuggingFace, product launches)
- [ ] Source diversity index tracking
- [ ] Hype calibration layer (cross-reference frequency with proxy metrics)
- [ ] LLM observability dashboards (Phoenix)
- [ ] Monthly calibration eval (test suite of known-good + known-noise signals)
- [ ] Hypothesis portfolio review process
- [ ] Remote Claude Code deployed on VPS as agent runtime

### Out of Scope

- Telegram delivery — briefings go to PWA + Obsidian vault only
- Voice TTS briefing — deferred to future iteration
- n8n workflows — using Make.com for scheduling/triggers instead
- Multi-user support — this is a personal system for Franklin only
- Real-time streaming — daily batch processing is sufficient

## Context

**Architecture shift from original spec:**
- **Orchestration:** Make.com for triggers/scheduling (originally n8n)
- **Agent runtime:** Remote Claude Code on VPS (needs setup)
- **Data backbone:** Weaviate (running on VPS, ready to use)
- **Vault integration:** Obsidian MCP for seed deposits and pattern queries
- **Briefing delivery:** PWA (Next.js + FastAPI, already live) — not Telegram
- **Agent models:** Claude Haiku (Scout scoring), Claude Sonnet (Analyst + Translator)

**Existing infrastructure:**
- Weaviate running on VPS via Docker — ready
- PWA live (Next.js frontend + FastAPI backend) — has daily brief, chat with coach, objectives/metrics
- Obsidian MCP running at mcp.ziksaka.com
- Make.com available (Franklin is Make employee)

**Pattern library status:** Conceptual with some entries — needs development alongside the system. Not enough to fully seed from day one.

**Predecessor:** Research Pattern Machine concept — becomes the Scout layer, but built from scratch.

**Code lives in:** Separate repo (this directory: ~/Projects/meridian). Planning docs here.

## Constraints

- **Agent runtime:** Remote Claude Code on VPS needs to be set up before agent workflows can run
- **Pattern bootstrap:** System needs patterns to match against — must build library in parallel with infrastructure
- **Solo operator:** Franklin is the only user and maintainer — architecture must be low-maintenance
- **Time:** ~14-16 hrs/week available outside day job
- **Cost awareness:** LLM token costs for daily scanning need monitoring (Phoenix in P5)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Make.com over n8n | Franklin works at Make, native expertise, trigger/webhook layer only | — Pending |
| Remote Claude Code as agent runtime | Full agent capabilities, not limited to Make scenario logic | — Pending |
| PWA for briefing + feedback | Already exists, avoids building new UI, natural daily touchpoint | — Pending |
| Weaviate as single backbone | Handles structured + semantic in one service, already deployed | — Pending |
| Three-tier gate (BRIEF/VAULT/ARCHIVE) | Nothing thrown away, but only best items consume attention | — Pending |
| Auto-deposit seeds, never auto-edit knowledge | Human friction on mature notes is the quality gate | — Pending |
| Obsidian-only delivery (no Telegram) | Vault is source of truth, PWA reads from it | — Pending |

---
*Last updated: 2026-03-13 after initialization*
