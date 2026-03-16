# Roadmap: Meridian (Forward Intelligence Radar)

## Milestones

- ✅ **v1.0 MVP** — Phases 1-4 (shipped 2026-03-16) — [Archive](milestones/v1.0-ROADMAP.md)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-4) — SHIPPED 2026-03-16</summary>

- [x] Phase 1: Foundation (3/3 plans) — completed 2026-03-14
- [x] Phase 2: Scout Pipeline (3/3 plans) — completed 2026-03-15
- [x] Phase 3: Intelligence + Briefing (2/2 plans) — completed 2026-03-15
- [x] Phase 4: Vault Integration (2/2 plans) — completed 2026-03-16

</details>

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 3/3 | Complete | 2026-03-14 |
| 2. Scout Pipeline | v1.0 | 3/3 | Complete | 2026-03-15 |
| 3. Intelligence + Briefing | v1.0 | 2/2 | Complete | 2026-03-15 |
| 4. Vault Integration | v1.0 | 2/2 | Complete | 2026-03-16 |

### Phase 5: LLM Observability

**Goal:** Phoenix dashboards for token cost monitoring, latency tracking, and pipeline performance visibility
**Requirements:** [OBS-01, OBS-02, OBS-03, OBS-04, OBS-05, OBS-06, OBS-07]
**Depends on:** Phase 4
**Plans:** 2/3 plans executed

Plans:
- [ ] 05-01-PLAN.md — OTel dependencies, tracer module, and test infrastructure
- [ ] 05-02-PLAN.md — Instrument invoke_claude() and all 4 pipeline stages with spans
- [ ] 05-03-PLAN.md — Wire init_tracing() into FastAPI startup + Phoenix UI smoke test
