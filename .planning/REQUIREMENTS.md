# Requirements: Meridian (Forward Intelligence Radar)

**Defined:** 2026-03-13
**Core Value:** Every morning, a useful briefing surfaces AI signals worth my attention — without me scanning anything manually.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Infrastructure

- [ ] **INFRA-01**: Weaviate collections deployed (signals, patterns, hypotheses, feedback) with locked schema
- [ ] **INFRA-02**: Pattern library bootstrapped with 15-20 seed patterns in Weaviate with example signals
- [ ] **INFRA-03**: Claude Code CLI installed and configured on VPS as agent runtime
- [ ] **INFRA-04**: FastAPI pipeline orchestrator deployed with Make.com webhook trigger endpoint and shared-secret auth

### Ingestion

- [ ] **INGEST-01**: Daily ArXiv fetch from cs.AI, cs.CL, cs.CV, cs.LG, cs.MA, cs.SD categories via arxiv 2.4.1
- [ ] **INGEST-02**: LLM relevance scoring (Claude Haiku) of each signal against pattern library (1-10 scale)

### Intelligence

- [ ] **INTEL-01**: Semantic source-to-pattern matching via Weaviate nearVector search
- [ ] **INTEL-02**: Signal clustering and trend detection across accumulated signals (Analyst agent, Claude Sonnet)

### Delivery

- [ ] **DELIV-01**: Morning briefing generated with top items, structured as: what's happening → time horizon → recommended action
- [ ] **DELIV-02**: Auto-deposit VAULT-tier signals as seeds to Obsidian vault via MCP

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Triage & Routing

- **TRIAGE-01**: Three-tier gate routing signals by score (BRIEF ≥7.0 / VAULT 5.0-6.9 / ARCHIVE <5.0)

### PWA Integration

- **PWA-01**: Briefing view integrated into existing Next.js + FastAPI PWA
- **PWA-02**: Signal feedback mechanism (rate each briefing item) in PWA

### Calibration

- **CAL-01**: Feedback-driven scoring calibration — weights auto-adjust based on ratings
- **CAL-02**: Monthly calibration eval with test suite (known-good + known-noise signals)

### Advanced Intelligence

- **ADV-01**: Hypothesis tracking with confidence scores and evidence linking
- **ADV-02**: Hype calibration layer (cross-reference social velocity vs research traction)
- **ADV-03**: Source diversity index tracking (no single source >50% of insights)
- **ADV-04**: Pattern library update proposals with REVIEW flag

### Source Expansion

- **SRC-01**: GitHub trending repos + starred AI/ML repos ingestion
- **SRC-02**: HuggingFace model/dataset release ingestion
- **SRC-03**: Google Patents / BigQuery patent signal ingestion
- **SRC-04**: Product Hunt / major product launch feed ingestion

### Observability

- **OBS-01**: Phoenix dashboards for LLM tracing (token usage, latency, cost per signal)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time streaming ingestion | ArXiv publishes in batches; daily batch is sufficient; streaming adds complexity without value |
| Telegram / push notifications | Briefing should be pulled intentionally, not push-interrupt deep work |
| Automatic knowledge note editing | Human friction on mature Obsidian notes is the quality gate; seeds only |
| Social media ingestion (Twitter/X, Reddit) | High-volume low-signal; use as hype calibration proxy only, not primary source |
| Full-text paper processing | Cost-prohibitive at scale; abstracts contain sufficient signal for scoring |
| Multi-user / sharing features | Personal system for one operator; no auth complexity |
| Voice/TTS briefing | Deferred; PWA reading experience is the target |
| Complex notification routing | One user, one briefing format; adjusts threshold, not routing rules |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | — | Pending |
| INFRA-02 | — | Pending |
| INFRA-03 | — | Pending |
| INFRA-04 | — | Pending |
| INGEST-01 | — | Pending |
| INGEST-02 | — | Pending |
| INTEL-01 | — | Pending |
| INTEL-02 | — | Pending |
| DELIV-01 | — | Pending |
| DELIV-02 | — | Pending |

**Coverage:**
- v1 requirements: 10 total
- Mapped to phases: 0
- Unmapped: 10 ⚠️

---
*Requirements defined: 2026-03-13*
*Last updated: 2026-03-13 after initial definition*
