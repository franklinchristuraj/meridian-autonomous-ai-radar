# Roadmap: Meridian (Forward Intelligence Radar)

## Overview

Meridian is built in four phases that follow a strict dependency chain: infrastructure and patterns must exist before Scout can score, Scout must prove its value before the downstream agents are built, and the vault integration is the final delivery layer. The system is useless without a bootstrapped pattern library, so it is co-developed with infrastructure in Phase 1 — not deferred. A hard validation gate sits between Phase 2 and Phase 3: no downstream agents are built until Franklin has read five consecutive briefings and confirmed the signal quality is meaningful.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Weaviate schema, FastAPI trigger wiring, VPS agent runtime, and pattern library bootstrapped in parallel (completed 2026-03-14)
- [ ] **Phase 2: Scout Pipeline** - Daily ArXiv ingestion, Haiku scoring against patterns, signals written to Weaviate with three-tier routing
- [ ] **Phase 3: Intelligence + Briefing** - Analyst agent clusters signals, Briefing agent generates the morning brief
- [ ] **Phase 4: Vault Integration** - Translator agent auto-deposits VAULT-tier seeds to Obsidian via MCP

## Phase Details

### Phase 1: Foundation
**Goal**: The system has a data backbone, a trigger layer, an agent runtime, and a populated pattern library — every prerequisite for the Scout pipeline to run correctly on day one
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04
**Success Criteria** (what must be TRUE):
  1. All five Weaviate collections (Signals, Patterns, Hypotheses, Feedback, Briefings) are deployed with locked schema and a round-trip test with 10 synthetic objects passes without error
  2. A Make.com scenario fires an HTTP POST to the FastAPI trigger endpoint and receives a 202 response within the timeout window
  3. Claude Code CLI is installed on the VPS, authenticated, and a headless `claude -p` invocation with `--output-format json` returns a parseable response
  4. At least 15 hand-crafted patterns covering LLMOps, agent architectures, RAG, evaluation, and tool use are queryable in Weaviate with example signals attached
**Plans**: 3 plans
Plans:
- [ ] 01-01-PLAN.md — Project skeleton, Weaviate schema, round-trip tests (INFRA-01)
- [ ] 01-02-PLAN.md — FastAPI trigger endpoint, Claude CLI wrapper (INFRA-03, INFRA-04)
- [ ] 01-03-PLAN.md — Pattern library bootstrap with 15+ seed patterns (INFRA-02)

### Phase 2: Scout Pipeline
**Goal**: Every morning, ArXiv papers from AI/ML categories are fetched, scored against the pattern library, routed through the three-tier gate, and written to Weaviate — reliably and cheaply
**Depends on**: Phase 1
**Requirements**: INGEST-01, INGEST-02, INTEL-01
**Success Criteria** (what must be TRUE):
  1. The Scout runs daily without manual intervention and a heartbeat file is written on each successful completion
  2. ArXiv papers from cs.AI, cs.CL, cs.CV, cs.LG, cs.MA, cs.SD are fetched, keyword-filtered, and stored as Signal objects in Weaviate with deduplication by ArXiv ID
  3. Each signal has a Haiku-generated relevance score (1-10) and a tier assignment (BRIEF / VAULT / ARCHIVE) based on semantic nearVector matching against the pattern library
  4. Franklin reads five consecutive morning briefings from the Scout-only output and confirms the signal distribution feels directionally correct before Phase 3 begins
**Plans**: 2 plans
Plans:
- [ ] 02-01-PLAN.md — Scout helper functions, tests, schema migration, arxiv dependency (INGEST-01, INGEST-02, INTEL-01)
- [ ] 02-02-PLAN.md — Pipeline orchestrator, trigger wiring, heartbeat (INGEST-01, INGEST-02, INTEL-01)

### Phase 3: Intelligence + Briefing
**Goal**: Scored signals are clustered into trends, mapped to patterns, and assembled into a structured morning briefing that Franklin can read
**Depends on**: Phase 2 (and validation gate: 5 consecutive briefings confirmed useful)
**Requirements**: INTEL-02, DELIV-01
**Success Criteria** (what must be TRUE):
  1. The Analyst agent clusters BRIEF and VAULT signals by topic and writes cluster IDs and matched pattern references back to Signal objects in Weaviate
  2. The Briefing agent generates a structured narrative brief (what's happening → time horizon → recommended action) and writes it to the Briefings collection in Weaviate
  3. Franklin can open the PWA and see today's briefing at `/briefing/today`, with BRIEF items visually prominent and a staleness warning if the pipeline has not run in over 25 hours
**Plans**: TBD
### Phase 4: Vault Integration
**Goal**: High-confidence VAULT-tier signals are automatically deposited as seeds in Franklin's Obsidian vault without any manual action required
**Depends on**: Phase 3
**Requirements**: DELIV-02
**Success Criteria** (what must be TRUE):
  1. The Translator agent deposits VAULT-tier signals with confidence >= 0.8 as seeds in Obsidian `01_seeds/` with the `#auto-deposit` tag and full provenance in frontmatter — without modifying any existing notes
  2. No more than 3 seeds are deposited per day regardless of how many signals qualify
  3. Seeds created by Translator are queryable in the vault and link back to the originating Signal in Weaviate via a source reference in their frontmatter
**Plans**: TBD
## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete   | 2026-03-14 |
| 2. Scout Pipeline | 0/2 | Not started | - |
| 3. Intelligence + Briefing | 0/TBD | Not started | - |
| 4. Vault Integration | 0/TBD | Not started | - |
