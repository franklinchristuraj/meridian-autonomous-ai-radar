# Project Research Summary

**Project:** Meridian — Autonomous Research Intelligence System
**Domain:** Personal AI signal monitoring pipeline (daily scan → score → briefing)
**Researched:** 2026-03-13
**Confidence:** HIGH (core stack and architecture verified against official sources; some pitfall specifics MEDIUM)

## Executive Summary

Meridian is a personal intelligence system, not a SaaS product. The correct mental model is a daily automated analyst: it scans ArXiv, scores signals against a personal pattern library, routes them through a three-tier gate (BRIEF / VAULT / ARCHIVE), and delivers a morning briefing Franklin actually reads. Experts build this type of system using a multi-agent pipeline — specialized agents for fetch/score, cluster/map, vault deposit, and briefing generation — each reading inputs from and writing outputs to a shared vector store (Weaviate) rather than passing data directly between processes. The pattern library is the true intelligence layer: without meaningful patterns to match against, scoring is noise. This makes pattern bootstrapping the first-mile problem, not the technical infrastructure.

The recommended approach is a FastAPI backend on an existing VPS, Make.com as a thin cron trigger only, Claude Agent SDK for the Analyst and Translator agents, direct Anthropic Haiku API for high-volume Scout scoring, Weaviate for all data persistence, and a Next.js PWA (already live) for delivery. Sentence-transformers with `nomic-embed-text-v1.5` handles local embedding with no ongoing API cost. The architecture is strictly sequential: Scout runs first, then Analyst, then Translator and Briefing in parallel. Weaviate is the message bus between stages — no direct agent-to-agent calls. This design makes every stage independently restartable and auditable.

The dominant risks are not technical. They are: (1) building too much before validating that Franklin reads and acts on the briefing at all (over-engineering trap), (2) launching without a bootstrapped pattern library, which produces briefings that feel random and kill confidence in the system before it matures, and (3) a feedback loop that becomes a filter bubble — the system learns to surface only what looks like the past. These three risks demand a hard validation gate after the first working pipeline, a pattern library as a Phase 1 deliverable in parallel with infrastructure, and a diversity floor built into scoring from day one.

---

## Key Findings

### Recommended Stack

The stack is constrained by existing infrastructure (Weaviate already on VPS, PWA already live, Make.com as Franklin's native orchestration tool) and should not deviate. Core decisions are: `weaviate-client` v4.20.x (gRPC performance, collections API), `claude-agent-sdk` 0.1.48 for agents that need MCP tool access (Analyst, Translator), direct `anthropic` SDK with Haiku for Scout scoring (cheaper, no full agent loop needed), `arxiv` 2.4.1 Python package, `sentence-transformers` 3.x with `nomic-embed-text-v1.5` (8192-token context, self-hosted, zero per-token cost). `arize-phoenix` OSS provides LLM observability with first-class Claude Agent SDK support. `uv` for Python package management, `apscheduler` 3.10.x for in-process scheduling, `httpx` for async HTTP.

**Core technologies:**
- `weaviate-client` 4.20.x: vector DB for Signals, Patterns, Hypotheses, Feedback, Briefings — already deployed, gRPC mode for performance
- `claude-agent-sdk` 0.1.48: headless subprocess agent for Analyst and Translator — needed for MCP tool calls and Obsidian integration
- `anthropic` (Haiku): direct API for Scout scoring — cheaper than full Agent SDK for a structured-output scoring task
- `sentence-transformers` + `nomic-embed-text-v1.5`: local embeddings, no API cost, 8192-token context handles full abstracts
- `arize-phoenix` OSS: LLM tracing and cost observability — self-hostable, OpenTelemetry-native
- `apscheduler` 3.10.x: in-process job scheduling inside FastAPI (no Redis/Celery needed at solo scale)
- Make.com: cron trigger only — fires HTTP POST to FastAPI; all agent logic on VPS

**Critical version requirements:**
- Python >=3.10 (Weaviate v4 type hint requirement)
- PyTorch CPU build for sentence-transformers on VPS without GPU
- APScheduler 3.10.x stable (4.x is still beta)

### Expected Features

Research against ArxivDigest, Scholar Inbox, Signal AI, and Paper Digest confirms the feature set in PROJECT.md is well-calibrated. The table stakes are the minimum to beat manual scanning; the differentiators (semantic pattern matching, hypothesis tracking, vault integration) are genuinely novel in the personal intelligence space — no comparable system does all three.

**Must have (table stakes — system is useless without these):**
- Daily ArXiv ingestion (cs.AI, cs.LG, cs.CL categories) — automated fetch
- Relevance scoring against pattern library — directional accuracy from day one
- Three-tier gate: BRIEF (≥7.0) / VAULT (5.0–6.9) / ARCHIVE (<5.0) — triage
- Morning briefing generation: top 5–10 BRIEF items with context — daily deliverable
- Briefing readable in PWA — touchpoint Franklin already uses
- Single-click feedback (thumbs up/down) per signal — frictionless feedback capture
- Persistent signal storage in Weaviate — required for pattern detection and audit
- Bootstrapped pattern library (15–20 patterns minimum) — the scoring brain

**Should have (differentiators — add after 2–3 weeks of v1 validation):**
- Vault auto-deposit of BRIEF seeds to Obsidian (seeds only, score ≥8.0, max 3/day)
- Source expansion: HuggingFace model releases, GitHub trending AI repos
- Signal clustering and trend detection (meaningful only after 2–4 weeks of data)
- Feedback-driven scoring calibration (meaningful only after 30–50 ratings)
- Source diversity index — track and warn when briefing narrows
- LLM cost observability via Phoenix

**Defer (v2+):**
- Hypothesis tracking with confidence scoring — requires mature signal history
- Hype calibration layer — requires multi-source ingestion first
- Monthly calibration eval test suite — requires 100+ labeled signals
- Full-text processing for top-tier papers
- Voice/TTS briefing

**Deliberately excluded (anti-features):**
- Real-time streaming ingestion (no daily-use benefit, adds infrastructure)
- Telegram/push notifications (interrupts deep work)
- Auto-editing mature Knowledge notes (destroys SPARK quality gate)
- Social media as primary ingestion source (amplifies hype before calibration is mature)
- LangChain (conflicts with Claude Agent SDK tool execution model)

### Architecture Approach

The system follows a four-layer architecture: a scheduling layer (Make.com cron → FastAPI 202 response), an agent runtime layer (four specialized agents running as `claude -p` subprocesses), a data backbone (five Weaviate collections as shared message bus), and a delivery layer (PWA + Obsidian vault). The sequential agent pipeline — Scout → Analyst → Translator/Briefing — uses Weaviate as the contract between stages, not direct inter-process communication. Each agent reads inputs from Weaviate, performs a narrow task, and writes structured outputs back to Weaviate. This makes every stage independently restartable and observable.

**Major components:**
1. **Make.com cron** — fires HTTP POST to `/trigger/scout` at 05:30, returns 202 immediately; contains no agent logic
2. **FastAPI trigger routers** — accept Make.com calls, dispatch background tasks, expose briefing/feedback/patterns API to PWA
3. **Scout Agent** (`claude -p`, Haiku) — fetch ArXiv, embed, score against pattern library, apply three-tier gate, write Signals to Weaviate
4. **Analyst Agent** (`claude -p`, Sonnet) — cluster BRIEF+VAULT signals, map to patterns, write cluster_id and matched_patterns back to Signal objects
5. **Translator Agent** (`claude -p`, Sonnet) — for BRIEF-tier signals: connect to vault knowledge via Obsidian MCP, deposit seeds with confidence threshold ≥0.8 and daily cap ≤3
6. **Briefing Agent** (`claude -p`, Sonnet) — curate top signals, generate narrative briefing, write to Weaviate Briefing collection
7. **Weaviate** — five collections: Signals, Patterns, Hypotheses, Feedback, Briefings; vector + structured metadata; shared state for all agents
8. **PWA (Next.js + FastAPI)** — serves briefings, captures feedback ratings, provides pattern browser
9. **Feedback loop** — nightly Make.com trigger → calibration job shifts pattern score weights (bounded: 0.5–2.0x multiplier, no model retraining)

**Key patterns:**
- Fire-and-forget trigger handoff (Make.com → FastAPI 202 → BackgroundTask) — avoids Make.com 60s timeout
- Headless Claude agent invocation via subprocess with `--output-format json` — enables programmatic agent runs
- Weaviate as shared state bus — each agent stage is independently restartable
- Rule-based weight shifting for feedback adaptation — no ML infrastructure, auditable, reversible

### Critical Pitfalls

1. **Pattern library cold start** — the system scores against nothing without patterns, producing low-quality briefings that kill confidence before it matures. Prevention: bootstrap 15–20 hand-crafted patterns covering LLMOps, agent architectures, evaluation, RAG, tool use as a Phase 1 deliverable in parallel with infrastructure. Do not run the first pipeline until this is done.

2. **Over-engineering before validation** — hypothesis tracking, auto-weight adjustment, and source diversity metrics built before a single briefing has been read. Prevention: define an explicit validation milestone (Franklin reads the briefing for 5 consecutive days and finds it useful) before any Phase 3+ features begin. The roadmap must have a hard gate.

3. **Agent cascading failure with silent errors** — a malformed Scout output produces plausible-sounding but wrong briefing content across multiple days without throwing an error. Prevention: Pydantic validation between every agent handoff; agents fail loudly; confidence fields on every output; Translator only deposits to vault above minimum confidence threshold.

4. **Weaviate schema lock-in** — changing property types after ingestion requires full re-import. Prevention: design all five collections on paper before writing code, disable auto-schema before first real data, store `schema_version` on every object, test full round-trip with 10 synthetic objects before any real ingestion.

5. **Scoring confirmation bias / filter bubble** — feedback loop amplifies over-represented patterns; novel signals stop surfacing. Prevention: build a diversity floor (minimum N distinct pattern clusters in BRIEF tier) from day one; apply novelty bonus to signals from under-represented clusters; decay-weight old ratings; monthly calibration against a held-out test set.

---

## Implications for Roadmap

The architecture research defines a build-order dependency chain that is strict. The roadmap should follow it without shortcuts. The pattern library and infrastructure must be co-developed in Phase 1 — this is the most important structural decision.

### Phase 1: Foundation + Pattern Library (parallel tracks)

**Rationale:** Nothing works without Weaviate schema and FastAPI trigger wiring. Nothing scores meaningfully without the pattern library. Both are blockers; both must be done first. Treating them as separate sequential phases is the cold start trap.

**Delivers:** Weaviate schema (all 5 collections) deployed and tested; FastAPI trigger endpoints returning 202; Make.com cron scenario wired; Claude Agent SDK installed and authenticated on VPS; 15–20 bootstrapped patterns with example signals; calibration test set of 30+ labeled signals created (held-out, not fed into pipeline).

**Addresses (from FEATURES.md):** Signal storage (Weaviate), pattern library bootstrap, scoring prerequisites.

**Avoids (from PITFALLS.md):** Schema lock-in (explicit schema, auto-schema disabled), pattern library cold start (15+ patterns before first run), embedding model drift (model pinned at collection creation).

**Research flag:** Standard patterns — Weaviate schema design and FastAPI setup are well-documented. No phase research needed.

---

### Phase 2: Scout Pipeline (ArXiv fetch + scoring)

**Rationale:** The core ingestion loop. Must work reliably and cheaply before building anything on top of it. Validates that the pattern library produces directionally correct scores against real papers.

**Delivers:** Daily ArXiv fetch (cs.AI, cs.LG, cs.CL), keyword pre-filter before LLM call, Haiku scoring against pattern library, three-tier gate, signals written to Weaviate with deduplication (ArXiv ID as deterministic UUID), heartbeat file written on each successful run.

**Uses (from STACK.md):** `arxiv` 2.4.1, `anthropic` Haiku, `weaviate-client` v4, `sentence-transformers` + `nomic-embed-text-v1.5`, `tenacity` for retry logic with caps.

**Implements (from ARCHITECTURE.md):** Scout Agent, Fire-and-forget trigger handoff, Weaviate Signal collection writes.

**Avoids (from PITFALLS.md):** LLM cost spiral (keyword pre-filter cuts 60–80% of papers before LLM call; Haiku not Sonnet; capped retries), agent cascading failure (Pydantic validation on Scout output before proceeding), Make.com trigger fragility (heartbeat file written on success).

**Validation gate (from PITFALLS.md):** Do not proceed to Phase 3 until Franklin has received and read 5 consecutive daily briefings from the Scout-only pipeline and confirmed directional signal quality is meaningful.

**Research flag:** Standard patterns — ArXiv API, Haiku scoring, Weaviate ingestion are well-documented. No phase research needed.

---

### Phase 3: Analyst + Translator + Briefing Agents

**Rationale:** Once Scout is producing reliable scored signals, the downstream agents can process them. All three agents depend on a populated Signal collection with meaningful scores, which only exists after Phase 2 validation.

**Delivers:** Analyst clustering and pattern mapping on BRIEF+VAULT signals; Translator vault seed deposit (confidence ≥0.8, max 3/day, `#auto-deposit` tag, provenance in frontmatter); Briefing agent generating narrative daily brief in Weaviate; PWA briefing route serving `/briefing/today`.

**Uses (from STACK.md):** `claude-agent-sdk` 0.1.48, Obsidian MCP, Sonnet for Analyst/Translator/Briefing, `pydantic` v2 for output validation.

**Implements (from ARCHITECTURE.md):** Analyst Agent, Translator Agent, Briefing Agent, sequential pipeline with Weaviate as shared state bus, parallel Translator + Briefing execution post-Analyst.

**Avoids (from PITFALLS.md):** Vault write contamination (confidence threshold + daily cap hard constraints in Translator), agent cascading failure (Pydantic validation at each handoff, confidence fields on outputs), auto-editing Knowledge notes (seeds only into `01_seeds/`, never modifying mature notes).

**Research flag:** May benefit from a brief phase research pass on Obsidian MCP `obs_create_note` behavior when called from a subprocess context, and on `claude -p` JSON output schema enforcement with `--json-schema` flag. These are narrow integration questions, not full research cycles.

---

### Phase 4: PWA Integration + Feedback Mechanism

**Rationale:** The briefing is generated but not readable in the PWA until routes and UI are wired. The feedback mechanism is table stakes — without it, scoring never improves and the calibration loop never starts.

**Delivers:** Next.js briefing page (`/briefing/today` and `/briefing/:date`), visual tier distinction (BRIEF prominent, VAULT collapsed), staleness indicator (warn if >25 hours since last run), one-tap feedback (thumbs up/down) per signal, feedback written to Weaviate Feedback collection, relative score context ("top 10% this week").

**Uses (from STACK.md):** FastAPI new routers for `/briefing`, `/feedback`, `/patterns`; Next.js frontend additions.

**Implements (from ARCHITECTURE.md):** PWA integration points, Feedback collection writes, pattern browser.

**Avoids (from PITFALLS.md):** Missing staleness indicator (pipeline failures go unnoticed), high-friction feedback UI (feedback not collected → scoring never improves), identical visual presentation of all briefing tiers.

**Research flag:** Standard patterns — FastAPI routing and Next.js page additions are well-documented. No phase research needed.

---

### Phase 5: Observability + Feedback Loop Calibration

**Rationale:** Only after 2–3 weeks of real usage is there enough feedback data (30–50 ratings minimum) to make weight adjustment meaningful. Observability infrastructure should come before automated weight adjustment — you need to see the costs and quality before tuning the loop.

**Delivers:** Arize Phoenix OSS deployed as Docker service; OpenTelemetry tracing on all agent runs; daily token cost per agent visible in Phoenix; nightly scoring-weight adjustment job (reads last 30 days Feedback, shifts pattern weights bounded 0.5–2.0x); daily token budget alert; source diversity metric tracked; monthly calibration eval run against held-out test set (created in Phase 1).

**Uses (from STACK.md):** `arize-phoenix` OSS, `opentelemetry-sdk`, `openinference-instrumentation-anthropic`, Prometheus + Grafana for Weaviate metrics.

**Implements (from ARCHITECTURE.md):** Feedback loop architecture, scoring weight adjustment, calibration process.

**Avoids (from PITFALLS.md):** Scoring confirmation bias (diversity floor in scoring; novelty bonus for under-represented clusters; decay-weighting old feedback), LLM cost spiral (Phoenix dashboard, daily budget alert), scoring drift going undetected (monthly calibration against held-out test set).

**Research flag:** Arize Phoenix OSS + Claude Agent SDK integration is MEDIUM confidence (GitHub README, not formal docs). A brief verification pass on the current instrumentation setup during planning is recommended before committing to Phoenix.

---

### Phase 6: Source Expansion + Intelligence Deepening (v1.x)

**Rationale:** ArXiv-only is the right starting point. Source expansion is only valuable after the core loop is calibrated — adding HuggingFace or GitHub signals to an uncalibrated system amplifies noise.

**Delivers:** HuggingFace model release ingestion, GitHub trending AI repos ingestion, source diversity index visible in PWA, signal clustering producing meaningful trend detection (possible after 4+ weeks of data accumulation).

**Avoids (from PITFALLS.md):** Hype calibration conflicts (social sources only after calibration is mature), source diversity blind spots.

**Research flag:** HuggingFace and GitHub API integration patterns are straightforward but will need a research pass on rate limits, authentication requirements, and signal schema normalization across source types before implementation.

---

### Phase Ordering Rationale

- **Pattern library is co-Phase-1** because scoring without patterns is not a degraded experience — it is a broken one. The pitfalls research is explicit: this is the most common reason personal intelligence systems fail in the first two weeks.
- **Scout pipeline is Phase 2 (not Phase 1)** because it depends on the schema being locked and patterns existing. Running Scout against an empty pattern library produces misleading calibration data.
- **Validation gate between Phase 2 and Phase 3** is mandatory. The over-engineering pitfall is the second most dangerous failure mode in this system. No Phase 3 work until 5 consecutive briefings have been read and confirmed useful.
- **Feedback mechanism (Phase 4) precedes the calibration loop (Phase 5)** because you cannot auto-adjust weights before you have ratings, and you cannot trust the calibration until you can observe the costs and quality in Phoenix.
- **Source expansion is last** because the calibration loop must be stable before adding new signal types that could distort scoring.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3:** Narrow verification pass on Obsidian MCP `obs_create_note` subprocess behavior and `claude -p --json-schema` enforcement. Not a full research cycle — targeted API check.
- **Phase 5:** Verify Arize Phoenix OSS + Claude Agent SDK current instrumentation setup. MEDIUM confidence source in STACK.md — confirm before committing.
- **Phase 6:** HuggingFace and GitHub API authentication, rate limits, and signal schema normalization across source types. MEDIUM complexity, standard patterns but needs scoping.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Weaviate schema design and FastAPI trigger setup — official docs, HIGH confidence throughout.
- **Phase 2:** ArXiv API, Haiku scoring, Weaviate ingestion — all well-documented with HIGH confidence sources.
- **Phase 4:** FastAPI routing additions and Next.js page additions — standard patterns, no unknowns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core decisions (Weaviate v4, Claude Agent SDK, ArXiv package, sentence-transformers) verified against official docs and PyPI. Arize Phoenix OSS integration is MEDIUM — GitHub README, not formal docs. |
| Features | HIGH | Table stakes validated against three comparable systems (ArxivDigest, Scholar Inbox, Signal AI). Feature dependency chain is well-reasoned. Solo-operator adaptations are inferred but coherent. |
| Architecture | HIGH | Core patterns (fire-and-forget trigger, headless subprocess agents, Weaviate as shared state) verified against official Claude Agent SDK, FastAPI, and Weaviate docs. Third-party orchestration blog is LOW confidence but corroborated. |
| Pitfalls | MEDIUM | Critical pitfalls (schema lock-in, cold start, cascading failure, cost spiral) are cross-verified across multiple sources. Make.com + Claude Agent SDK combination has limited public post-mortems. Confirmation bias / filter bubble section has strong academic backing. |

**Overall confidence:** HIGH

### Gaps to Address

- **Arize Phoenix + Claude Agent SDK instrumentation**: MEDIUM confidence source in STACK.md. Before committing Phoenix as the observability layer, verify current instrumentation support against the live GitHub repo or docs during Phase 5 planning.
- **`claude -p --json-schema` enforcement**: The headless invocation pattern with structured JSON output and schema enforcement is documented but behavior under edge cases (context overflow, model refusal) is not fully characterized. Build explicit fallback and validation in Phase 3.
- **Obsidian MCP subprocess behavior**: Calling `obs_create_note` from a Python subprocess via the Claude Agent SDK is a novel integration path. Verify the MCP stdio connection survives the subprocess lifecycle before Phase 3 begins.
- **ArXiv daily volume variance**: Research estimates 200–400 papers/day in AI/ML categories. The keyword pre-filter should cut this to 40–80 for LLM scoring. Actual numbers should be measured in Phase 2 before committing to cost estimates.
- **Make.com operations budget**: STACK.md notes Franklin is a Make employee. Confirm scenario operation limits for the account tier in use before designing the cron + calibration trigger architecture.

---

## Sources

### Primary (HIGH confidence)
- [Weaviate Python Client v4 docs](https://docs.weaviate.io/weaviate/client-libraries/python) — collections API, schema design, hybrid search, quantization
- [Weaviate Hybrid Search docs](https://docs.weaviate.io/weaviate/search/hybrid) — alpha parameter, tokenization, reranker integration
- [arxiv PyPI](https://pypi.org/project/arxiv/) + [arxiv.py GitHub](https://github.com/lukasschwab/arxiv.py) — rate limiting, delay_seconds pattern
- [claude-agent-sdk PyPI](https://pypi.org/project/claude-agent-sdk/) — v0.1.48 current
- [Anthropic Agent SDK hosting docs](https://platform.claude.com/docs/en/agent-sdk/hosting) — persistent container mode, VPS deployment
- [FastAPI BackgroundTasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) — fire-and-forget pattern
- [Make.com webhooks docs](https://help.make.com/webhooks) — trigger patterns, timeout behavior
- [Claude Code headless / Agent SDK CLI](https://code.claude.com/docs/en/headless) — `claude -p` invocation pattern
- [Weaviate collection definitions](https://docs.weaviate.io/weaviate/starter-guides/managing-collections) — schema management
- [Weaviate cross-references](https://docs.weaviate.io/weaviate/manage-collections/cross-references) — explicit caution against overuse
- [Weaviate Best Practices](https://docs.weaviate.io/weaviate/best-practices) — schema design, quantization, memory management

### Secondary (MEDIUM confidence)
- [ArxivDigest GitHub](https://github.com/AutoLLM/ArxivDigest) — relevance scoring approach, 1-10 LLM scoring pattern
- [Scholar Inbox paper (arXiv:2504.08385)](https://arxiv.org/abs/2504.08385) — active learning feedback loop, rating-driven adaptation
- [nomic-embed-text-v1.5 HuggingFace](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) — 8192 context, Matryoshka support, sentence-transformers compatibility
- [Arize Phoenix GitHub](https://github.com/Arize-ai/phoenix) — self-hosted, Claude Agent SDK support
- [APScheduler + FastAPI patterns](https://rajansahu713.medium.com/implementing-background-job-scheduling-in-fastapi-with-apscheduler-6f5fdabf3186) — lifespan pattern
- [Embedding Drift: The Quiet Killer — DEV Community](https://dev.to/dowhatmatters/embedding-drift-the-quiet-killer-of-retrieval-quality-in-rag-systems-4l5m) — detection patterns
- [Why Multi-Agent AI Systems Fail — Galileo](https://galileo.ai/blog/multi-agent-ai-failures-prevention) — cascading error patterns
- [Agentic RAG survey (ArXiv 2501.09136)](https://arxiv.org/abs/2501.09136) — pipeline patterns
- [LLM Cost Optimization Guide — FutureAGI](https://futureagi.com/blogs/llm-cost-optimization-2025) — daily usage cost structures

### Tertiary (LOW confidence)
- [all-MiniLM-L6-v2 deprecation discussion](https://news.ycombinator.com/item?id=46081800) — community consensus against new deployments; use as negative signal only
- [Claude Agent SDK orchestration patterns (Skywork AI blog)](https://skywork.ai/blog/claude-agent-sdk-best-practices-ai-agents-2025/) — corroborated by official docs

---
*Research completed: 2026-03-13*
*Ready for roadmap: yes*
