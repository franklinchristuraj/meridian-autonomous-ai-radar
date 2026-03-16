# Retrospective

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-16
**Phases:** 4 | **Plans:** 10 | **Timeline:** 4 days (2026-03-13 → 2026-03-16)

### What Was Built
- Weaviate schema (5 collections) with idempotent migrations and 16 seed patterns
- FastAPI orchestrator with X-API-Key auth, Make.com webhook integration, APScheduler cron
- Scout pipeline: daily ArXiv fetch from 6 categories, Claude Haiku scoring, three-tier routing
- Analyst agent: semantic signal clustering, trend detection, pattern-anchor mapping
- Briefing agent: Claude Sonnet narrative generation, staleness detection, 5 API endpoints
- Translator agent: VAULT-tier seed deposit to Obsidian vault with duplicate detection and daily cap
- 116 tests across all modules with TDD workflow

### What Worked
- **TDD throughout**: Writing tests first caught schema issues early (e.g., missing `confidence` property discovered during Phase 4 research)
- **Wave-based parallel execution**: Independent plans within a phase ran simultaneously, cutting wall-clock time
- **Lazy import pattern for pipeline chaining**: Each stage independently testable, no circular imports
- **Idempotent schema migrations**: Safe to re-run, no state management needed
- **Context-gathering before planning**: discuss-phase sessions front-loaded decisions, so planners had clear specs

### What Was Inefficient
- INFRA-01 checkbox never got checked despite being complete — manual traceability tracking drifts
- One-liner fields in SUMMARY.md were never populated by executors — summary-extract returned nulls
- Performance metrics in STATE.md were inconsistently tracked across phases
- ctx_batch_execute sandbox couldn't access project files — had to fall back to Read tool for codebase scouting

### Patterns Established
- Pipeline function shape: fetch → process → write → chain next stage
- Schema migration pattern: `_migrate_signals_{property}` with idempotent add-property
- Lazy import wrapper for pipeline chaining: `_run_next_pipeline()` inside try block
- Heartbeat JSON files per pipeline stage for monitoring
- Agent model selection: Haiku for high-volume cheap tasks, Sonnet for reasoning

### Key Lessons
- Co-developing patterns with infrastructure (Phase 1) was the right call — Scout would have been useless without them
- Direct filesystem write to Obsidian vault was simpler and more reliable than MCP server integration
- Post-query filtering in Python (confidence >= 0.8) trades query efficiency for None-safety — revisit at scale
- 25-hour staleness threshold > 24 hours prevents false alerts from scheduling drift

### Cost Observations
- Model mix: ~70% Haiku (scoring), ~30% Sonnet (clustering + briefing + translation)
- Sessions: 6 (init + 4 phase executions + milestone completion)
- Notable: Phase 4 execution was fastest (~18min for 2 plans) due to established patterns

## Cross-Milestone Trends

| Metric | v1.0 |
|--------|------|
| Phases | 4 |
| Plans | 10 |
| Tests | 116 |
| Python LOC | ~4,670 |
| Timeline | 4 days |
| Commits | 30 |
