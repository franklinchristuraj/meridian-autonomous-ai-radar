# Feature Research

**Domain:** Personal research intelligence / AI signal monitoring system
**Researched:** 2026-03-13
**Confidence:** HIGH (core features well-validated by comparable systems; solo-operator adaptations are reasoned inferences)

---

## Context: What This System Is

Meridian is not a SaaS product. It is a personal intelligence system for one operator (Franklin) whose primary job is staying ahead of the AI landscape without manually scanning hundreds of papers and signals daily. The goal is compressed time-to-take, not comprehensive coverage.

This distinction reshapes every feature decision:
- "Users" = one person with established preferences and existing context (Obsidian vault)
- "Competition" = manual scanning + AI newsletters + random Twitter/X signal
- "Table stakes" = the minimum to be materially better than that baseline
- "Differentiators" = what makes this system genuinely intelligent rather than just automated

---

## Feature Landscape

### Table Stakes (System Is Useless Without These)

Features that must exist for the system to deliver its core promise: a daily briefing containing only the signals worth attention.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Daily signal ingestion (ArXiv) | Without automated fetch, Franklin must scan manually — the entire value disappears | LOW | ArXiv API is stable and well-documented; daily batch is sufficient |
| Relevance scoring against personal interests | Without scoring, ingestion produces a firehose not a briefing | MEDIUM | Requires a defined interest profile or pattern library to score against; LLM-based scoring (1-10 scale) is proven pattern (ArxivDigest, Scholar Inbox) |
| Three-tier triage gate | Without routing, every signal competes equally for attention — alert fatigue guaranteed | LOW | BRIEF (≥7.0) / VAULT (5.0–6.9) / ARCHIVE (<5.0); thresholds are tunable |
| Morning briefing generation | The daily deliverable — structured output of top-tier signals with context | MEDIUM | Must surface "why this matters now," not just what the paper says; briefing without context is a worse ArXiv email |
| Briefing delivery to existing touchpoint | Without delivery to a place Franklin already checks, adoption fails | LOW | PWA already live; Obsidian vault already in daily workflow — both are viable |
| Basic feedback mechanism | Without feedback, scoring never improves and the system stays calibrated to initial assumptions | LOW | Thumbs up/down or star rating per signal; must be frictionless (PWA or vault inline) |
| Persistent signal storage | Signals must be retained across sessions for pattern detection, hypothesis tracking, and audit | MEDIUM | Weaviate already deployed; vector storage enables both semantic retrieval and structured queries |
| Source-to-pattern matching | Scoring without a reference pattern library scores against nothing; patterns define "relevant" | HIGH | Bootstrapping the pattern library is the hardest first-mile problem; must co-develop with ingestion |

---

### Differentiators (What Makes This Actually Intelligent)

Features that distinguish Meridian from a fancy ArXiv email subscription.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Pattern library with semantic matching | Scoring against Franklin's actual conceptual landscape (LLMOps, agentic systems, automation) rather than keyword lists — finds papers Franklin would find, not just papers with matching terms | HIGH | Weaviate semantic search is the right primitive; pattern library must be maintained as concepts evolve; this is the "brain" of the system |
| Signal clustering and trend detection | Surfaces "five papers this week are all pointing toward the same shift" — what no individual paper could show | HIGH | Analyst agent clusters across BRIEF + VAULT tiers; meaningful only after 2–4 weeks of signal accumulation |
| Hypothesis tracking with confidence evolution | Transforms passive reading into active belief-state management; Franklin tracks "I believe X is becoming true" and the system surfaces evidence for/against | HIGH | Unique to personal intelligence systems; no off-the-shelf tool does this well; requires hypothesis schema + signal-to-hypothesis linking |
| Vault integration — auto-deposit seeds | Connects signals to Franklin's existing knowledge infrastructure; seeds land in Obsidian ready for processing | MEDIUM | Obsidian MCP already available; auto-deposit for seeds is lower risk than auto-editing mature notes |
| Hype calibration layer | Flags signals inflated by social velocity vs. genuine research traction — cross-references citation patterns, code release, and reproduction evidence | HIGH | Distinguishes "Twitter is excited" from "this actually works"; citation velocity + GitHub stars + HuggingFace model downloads as proxies; keeps briefing credible |
| Source diversity index | Tracks breadth of signal sources to prevent echo-chamber scoring — surfacing when briefing has been drawn from too narrow a source set | MEDIUM | Tracks source distribution across ingested signals; warns when diversity drops below threshold; prevents systematic blind spots |
| Feedback-driven scoring calibration | Scoring weights adjust based on Franklin's signal ratings — system gets more accurate over time without manual reconfiguration | HIGH | Active learning loop: Scholar Inbox validates this approach; requires sufficient rating data to move weights meaningfully (30–50 ratings minimum before visible drift) |
| LLM cost observability | Tracks token spend per agent run; surfaces when daily scanning becomes expensive without producing proportional briefing quality | MEDIUM | Phoenix (Arize) for LLM tracing; cost-per-BRIEF-item is the useful metric; important for solo operator without budget backstop |
| Monthly calibration eval | Structured review: test suite of known-good signals (should score ≥7.0) and known-noise signals (should score <5.0); surfaces scoring drift before it compounds | MEDIUM | Prevents silent degradation; without this, the system can drift toward mediocrity without anyone noticing |

---

### Anti-Features (Deliberately Excluded)

Features that seem valuable but create problems for a solo-operator personal intelligence system.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time streaming ingestion | "Stay current with breaking AI news" | ArXiv publishes in batches; real-time streaming adds infrastructure complexity with no daily-use benefit; streaming creates pressure to check constantly, defeating the "morning briefing" model | Daily batch at consistent time; Make.com scheduled trigger is sufficient |
| Telegram / push notification delivery | Immediate alert to phone for high-score signals | Push interrupts deep work; a personal intelligence system should be consulted, not interrupt; the briefing model requires intentional consumption | PWA + Obsidian vault delivery; Franklin pulls when ready |
| Automatic knowledge note creation | "Save time, auto-populate vault" | Auto-editing mature Obsidian notes destroys hard-won knowledge structure; the quality gate is human friction | Auto-deposit seeds only (lowest SPARK tier); Franklin decides promotion |
| Multi-source social monitoring (Twitter/X, Reddit) | Social signals amplify noise; AI Twitter is high-volume low-signal | Social velocity is a proxy for hype, not validity; adding social ingestion inflates noise dramatically before calibration is mature | Use social velocity as a hype calibration signal only, not as a primary ingestion source; cross-reference post-hoc |
| Full-text paper processing (vs. abstract) | "More information = better scoring" | Full-text processing 30–50 papers/day at Sonnet tier is cost-prohibitive; abstracts contain sufficient signal for relevance scoring; full-text processing for BRIEF-tier papers only is a later optimization | Abstract-based scoring for triage; full-text summarization only for top-scoring papers entering the briefing |
| Complex notification routing rules | "Alert me differently based on topic category" | Routing logic becomes a maintenance burden; for one user, a consistent daily briefing is always better than conditional routing that requires tuning | Single briefing format; Franklin adjusts threshold, not routing rules |
| Collaborative features / sharing | "Share interesting papers with team" | Adds auth complexity and social dynamics to a personal system; scope creep that delays core functionality | Out of scope entirely; point to paper directly if sharing is needed |
| Voice/TTS briefing | "Listen while commuting" | Additional delivery pipeline to maintain; briefing format optimized for reading (structured lists, scores, links) doesn't translate well to audio without separate synthesis | Deferred to v2+; the PWA reading experience is the target |

---

## Feature Dependencies

```
[Pattern Library]
    └──required by──> [Relevance Scoring]
                          └──required by──> [Three-Tier Gate]
                                                └──required by──> [Briefing Generation]
                                                                      └──required by──> [Feedback Mechanism]

[Signal Storage (Weaviate)]
    └──required by──> [Pattern Library]
    └──required by──> [Signal Clustering]
    └──required by──> [Hypothesis Tracking]

[Feedback Mechanism]
    └──enables──> [Scoring Calibration (auto-adjust weights)]

[Signal Clustering]
    └──requires 2-4 weeks of data──> [Meaningful Trend Detection]

[Hype Calibration]
    └──enhances──> [Relevance Scoring] (downweights socially amplified signals)
    └──requires──> [Source Diversity Tracking] (to know what sources are in play)

[Vault Integration]
    └──requires──> [Briefing Generation] (seeds come from briefing-tier signals)
    └──requires──> [Obsidian MCP] (already available)

[LLM Observability]
    └──independent──> [All agent runs] (cross-cutting concern, not a dependency)

[Monthly Calibration Eval]
    └──requires──> [Feedback Mechanism] (needs rated signals to evaluate against)
    └──requires──> [Scoring system] (needs a stable scoring model to evaluate)
```

### Dependency Notes

- **Pattern Library requires Signal Storage:** Patterns must live somewhere queryable; Weaviate is the right home. If Weaviate is not ready, no meaningful scoring is possible.
- **Relevance Scoring requires Pattern Library:** You cannot score a signal's relevance without a definition of what "relevant" means. Bootstrapping the pattern library is the true Day 1 blocker.
- **Scoring Calibration requires Feedback:** Auto-adjusting weights requires rated signal history. The feedback loop must accumulate 30–50 ratings before weight drift is statistically meaningful.
- **Signal Clustering requires data accumulation:** Clustering 3 signals is meaningless. This feature becomes valuable after 2–4 weeks of daily ingestion and triage.
- **Hypothesis Tracking is independent but low-value without Signal Clustering:** Hypotheses can be seeded manually, but the system's ability to surface evidence for/against a hypothesis improves significantly when clustering identifies thematic signal groups.
- **Hype Calibration conflicts with early source expansion:** Adding social sources before calibration is mature will systematically inflate scores for hyped topics. Social signals should enter only as calibration inputs, not primary ingestion.

---

## MVP Definition

### Launch With (v1)

The minimum to validate the core loop: signals in, triage out, briefing delivered, feedback captured.

- [ ] Daily ArXiv ingestion (cs.AI, cs.LG, cs.CL categories) — proves automated fetch works
- [ ] Relevance scoring against bootstrapped pattern library (even 10–15 patterns is enough to start) — proves scoring is directionally correct
- [ ] Three-tier gate (BRIEF / VAULT / ARCHIVE) — proves triage works
- [ ] Morning briefing generation with top 5–10 BRIEF-tier items — proves value delivery
- [ ] Briefing readable in PWA — proves daily touchpoint is viable
- [ ] Single-click feedback (thumbs up/down) per signal — proves feedback capture is frictionless

### Add After Validation (v1.x)

Add once Franklin has used v1 for 2–3 weeks and confirmed the briefing is useful.

- [ ] Vault auto-deposit of BRIEF seeds to Obsidian — trigger: "I keep manually creating seeds from the briefing"
- [ ] Source expansion (HuggingFace model releases, GitHub trending AI repos) — trigger: "ArXiv alone is missing signals I care about"
- [ ] Signal clustering / trend detection — trigger: "I'm noticing themes the briefing isn't surfacing explicitly"
- [ ] Feedback-driven scoring calibration — trigger: "My ratings suggest the default weights are miscalibrated"
- [ ] Source diversity index — trigger: "I want to know how narrow my signal sources are"
- [ ] LLM cost observability (Phoenix) — trigger: "I want to understand what each agent run costs"

### Future Consideration (v2+)

Features with genuine value but requiring mature signal history or significant build effort.

- [ ] Hypothesis tracking with confidence scoring — requires: established signal history + pattern library maturity + Franklin actively wants to track beliefs
- [ ] Hype calibration layer — requires: multi-source ingestion to cross-reference; premature before source expansion is stable
- [ ] Monthly calibration eval (test suite) — requires: enough rated signals to build a meaningful test set (100+ ratings minimum)
- [ ] Full-text processing for top-tier papers — requires: cost observability to know this is affordable
- [ ] Voice/TTS briefing — requires: explicit request; not a current constraint

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Daily ArXiv ingestion | HIGH | LOW | P1 |
| Pattern library (bootstrap) | HIGH | HIGH | P1 |
| Relevance scoring | HIGH | MEDIUM | P1 |
| Three-tier gate | HIGH | LOW | P1 |
| Briefing generation | HIGH | MEDIUM | P1 |
| PWA delivery | HIGH | LOW (already exists) | P1 |
| Feedback mechanism | HIGH | LOW | P1 |
| Signal storage (Weaviate) | HIGH | LOW (already deployed) | P1 |
| Vault auto-deposit (seeds) | MEDIUM | MEDIUM | P2 |
| Source expansion | MEDIUM | MEDIUM | P2 |
| Signal clustering | HIGH | HIGH | P2 |
| Feedback-driven calibration | HIGH | HIGH | P2 |
| Source diversity index | MEDIUM | MEDIUM | P2 |
| LLM cost observability | MEDIUM | LOW | P2 |
| Hypothesis tracking | HIGH | HIGH | P3 |
| Hype calibration layer | HIGH | HIGH | P3 |
| Monthly calibration eval | MEDIUM | MEDIUM | P3 |
| Full-text processing | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch — system does not function without these
- P2: Should have — add after v1 is validated (weeks 3–8)
- P3: Future — add once signal history and usage patterns are established

---

## Comparable System Analysis

| Feature | ArxivDigest | Scholar Inbox | Signal AI | Paper Digest | Meridian Approach |
|---------|-------------|---------------|-----------|--------------|-------------------|
| Relevance scoring | 1-10 via LLM against natural-language interest profile | Transformer embeddings; active learning from ratings | Multi-source with social amplification scoring | Citation-backed summaries | LLM scoring (Haiku for cost) against Weaviate pattern library |
| Feedback loop | None | Rating-driven active learning; adapts recommendations | Engagement metrics | None stated | Thumbs up/down per signal; weight auto-adjustment over time |
| Source diversity | Single source (ArXiv) | Multiple open-access archives | 226 markets, 75 languages | Multiple sources | Starts ArXiv-only; index tracks diversity as sources expand |
| Pattern/interest model | Natural language config file | Learned from ratings | Risk taxonomy (15 pillars) | None stated | Weaviate semantic patterns; maintained as living library |
| Hypothesis tracking | None | None | None | None | Novel; personal belief-state management against signal evidence |
| Vault/PKM integration | None | None | None | None | Novel; Obsidian MCP for seed deposit |
| Hype calibration | None | None | Social Amplification Score | None | Novel; proxy metrics (citation velocity, code release, reproduction) |
| Delivery | Email, web UI | Email, web UI | Dashboard | Email, web UI | PWA (existing) + Obsidian |

---

## Sources

- [ArxivDigest on GitHub](https://github.com/AutoLLM/ArxivDigest) — relevance scoring approach, natural language interest profile, 1-10 LLM scoring pattern
- [Scholar Inbox: Personalized Paper Recommendations for Scientists (arXiv:2504.08385)](https://arxiv.org/abs/2504.08385) — active learning feedback loop, transformer-based embedding, rating-driven adaptation
- [Signal AI 2025 overview](https://signal-ai.com/insights/2025-at-signal-ai-elevating-reputation-risk-intelligence/) — Social Amplification Score, multi-source ingestion, early warning architecture
- [ChampSignal on competitive intelligence tools](https://champsignal.com/blog/competitive-intelligence-software) — statistical outlier detection for alert fatigue prevention
- [Reducing Alert Fatigue via AI (IBM)](https://www.ibm.com/think/insights/alert-fatigue-reduction-with-ai-agents) — alert fatigue anti-pattern analysis; human-in-loop design
- [Paper Digest platform](https://www.paperdigest.org/) — daily digest features, topic tracking, citation-backed summaries
- [Deloitte: Cutting through the noise — Tech signals worth tracking](https://www.deloitte.com/us/en/insights/topics/technology-management/tech-trends/2026/2026-technology-signals.html) — signal vs. noise calibration framing
- [Confidence Scoring in Threat Intelligence (Cyware)](https://www.cyware.com/resources/security-guides/what-is-confidence-scoring-in-threat-intelligence) — confidence score design (0-100), frequency, quality, relevance dimensions
- [ResearchRabbit](https://www.researchrabbit.ai/) — citation network visualization, related paper discovery
- [Scholar Inbox platform](https://www.scholar-inbox.com/) — personalized research recommendations with active learning

---

*Feature research for: Personal research intelligence / AI signal monitoring (Meridian)*
*Researched: 2026-03-13*
