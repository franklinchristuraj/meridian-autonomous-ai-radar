# Architecture Research

**Domain:** Autonomous research intelligence pipeline (agentic RAG + scheduled briefing)
**Researched:** 2026-03-13
**Confidence:** HIGH (core patterns verified against official Claude Agent SDK docs, Weaviate docs, Make.com docs, FastAPI docs)

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        SCHEDULING LAYER                              │
│  ┌──────────────┐    ┌─────────────────────────────────────────────┐ │
│  │  Make.com    │───▶│  HTTP POST → FastAPI /trigger endpoint      │ │
│  │  (cron/      │    │  on VPS (Meridian backend)                  │ │
│  │   webhook)   │    └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        AGENT RUNTIME LAYER (VPS)                     │
│                                                                      │
│  FastAPI /trigger → background task → claude -p (headless)          │
│                                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────────┐ │
│  │ Scout Agent  │   │ Analyst Agent│   │   Briefing Agent         │ │
│  │ (Haiku)      │   │ (Sonnet)     │   │   (Sonnet)               │ │
│  │ fetch+score  │──▶│ cluster+map  │──▶│   curate+format          │ │
│  └──────────────┘   └──────────────┘   └──────────────────────────┘ │
│                              │                     │                 │
│                    ┌─────────┘                     │                 │
│                    ▼                               ▼                 │
│           ┌────────────────┐              ┌───────────────┐         │
│           │ Translator     │              │ Obsidian MCP  │         │
│           │ Agent (Sonnet) │              │ seed deposit  │         │
│           └───────┬────────┘              └───────────────┘         │
└───────────────────┼──────────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        DATA BACKBONE (VPS)                           │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐   │
│  │   Signal       │  │   Pattern      │  │   Hypothesis        │   │
│  │   collection   │  │   library      │  │   collection        │   │
│  │   (Weaviate)   │  │   (Weaviate)   │  │   (Weaviate)        │   │
│  └────────────────┘  └────────────────┘  └─────────────────────┘   │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐                            │
│  │   Feedback     │  │   Briefing     │                            │
│  │   collection   │  │   collection   │                            │
│  │   (Weaviate)   │  │   (Weaviate)   │                            │
│  └────────────────┘  └────────────────┘                            │
└──────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        DELIVERY LAYER                                │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  PWA (Next.js frontend + FastAPI backend)                   │    │
│  │  - /briefing  → renders today's BRIEF-tier items            │    │
│  │  - /feedback  → star ratings, signal dismissal              │    │
│  │  - /patterns  → browse + edit pattern library               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Obsidian vault (via MCP)                                   │    │
│  │  - BRIEF items → seeds deposited automatically              │    │
│  │  - Human reviews vault; promotes seeds to projects/knowledge│    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
                    │
                    ▼ (feedback writes back to Weaviate)
            [Scoring weights adjust over time]
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| Make.com cron | Daily trigger at 05:30 local time; send HTTP POST to FastAPI `/trigger/scout` | Make HTTP module → VPS endpoint |
| FastAPI `/trigger/*` endpoints | Receive Make.com calls, return 202 immediately, dispatch background tasks | FastAPI BackgroundTasks or ARQ worker |
| Scout Agent | Fetch ArXiv (and future sources), embed, score each paper against pattern library, apply three-tier gate | `claude -p` headless, Haiku model, writes to Weaviate Signal collection |
| Analyst Agent | Cluster scored BRIEF+VAULT signals, map to patterns, surface new pattern candidates | `claude -p` headless, Sonnet model, reads/writes Weaviate |
| Translator Agent | For BRIEF-tier items: connect signal to vault knowledge, compose seed text, deposit via Obsidian MCP | `claude -p` headless, Sonnet model, calls Obsidian MCP |
| Briefing Agent | Curate top signals into daily briefing document, write to Weaviate Briefing collection + PWA-readable endpoint | `claude -p` headless, Sonnet model |
| Weaviate | Vector + structured metadata store for all collections; semantic search backbone | Docker on VPS, Python weaviate-client v4 |
| PWA (Next.js + FastAPI) | Read and display briefings; collect feedback ratings; pattern browser | Already live; new routes added incrementally |
| Obsidian MCP | Deposit seeds into vault `01_seeds/`; optionally query pattern library from vault | mcp.ziksaka.com, existing connection |
| Feedback loop | User ratings in PWA write to Weaviate Feedback collection; scoring weights re-computed nightly | Lightweight score adjustment job, no retraining |

---

## Recommended Project Structure

```
meridian/
├── agents/                    # Claude Code headless invocation scripts
│   ├── scout.py               # ArXiv fetch + Haiku scoring pipeline
│   ├── analyst.py             # Cluster + pattern mapping (Sonnet)
│   ├── translator.py          # Vault seed deposit via Obsidian MCP (Sonnet)
│   ├── briefing.py            # Briefing generation (Sonnet)
│   └── prompts/               # System prompts per agent (versioned)
│       ├── scout_system.md
│       ├── analyst_system.md
│       ├── translator_system.md
│       └── briefing_system.md
├── api/                       # FastAPI backend (extends existing PWA backend)
│   ├── routers/
│   │   ├── trigger.py         # Make.com inbound webhooks → background tasks
│   │   ├── briefing.py        # GET /briefing/today, GET /briefing/:date
│   │   ├── feedback.py        # POST /feedback/:signal_id
│   │   └── patterns.py        # GET/POST/PATCH pattern library
│   ├── tasks/                 # Background task implementations
│   │   ├── run_scout.py
│   │   ├── run_analyst.py
│   │   ├── run_translator.py
│   │   └── run_briefing.py
│   └── main.py                # Existing FastAPI app — mount new routers
├── db/                        # Weaviate schema definitions + client helpers
│   ├── schema.py              # Collection definitions (authoritative)
│   ├── client.py              # Weaviate connection singleton
│   └── collections/
│       ├── signals.py
│       ├── patterns.py
│       ├── hypotheses.py
│       ├── feedback.py
│       └── briefings.py
├── lib/                       # Shared utilities
│   ├── arxiv.py               # ArXiv API fetch + normalization
│   ├── embed.py               # Embedding wrapper (Weaviate vectorizer or external)
│   ├── scoring.py             # Three-tier gate logic + weight application
│   └── obsidian.py            # Obsidian MCP client wrapper
├── scripts/                   # One-time setup / maintenance scripts
│   ├── bootstrap_patterns.py  # Seed initial pattern library
│   └── migrate_schema.py      # Schema evolution helpers
├── tests/
│   ├── eval/                  # Monthly calibration test suite
│   │   ├── known_good.json    # Signals that should score BRIEF
│   │   └── known_noise.json   # Signals that should score ARCHIVE
│   └── unit/
├── .planning/                 # Project planning (this dir)
└── docker-compose.yml         # Weaviate + any supporting services
```

### Structure Rationale

- **agents/**: Each agent is a standalone Python script that invokes `claude -p` headlessly. Keeping prompts as versioned `.md` files in `agents/prompts/` enables prompt evolution without touching code.
- **api/routers/trigger.py**: The Make.com handoff surface is a single router. It does nothing except accept the call, return 202, and enqueue. This keeps the trigger contract stable while agent implementation evolves.
- **db/schema.py**: Single authoritative source for all Weaviate collection definitions. Schema changes run through `migrate_schema.py` — never mutated ad-hoc.
- **lib/scoring.py**: The three-tier gate (BRIEF ≥7.0 / VAULT 5.0–6.9 / ARCHIVE <5.0) is isolated here. Score weights are stored in Weaviate (or a config file) and this module reads them — enabling feedback-driven adjustment without code changes.

---

## Architectural Patterns

### Pattern 1: Fire-and-Forget Trigger Handoff

**What:** Make.com POSTs to FastAPI; FastAPI returns 202 immediately and dispatches the pipeline as a background task. Make.com does not wait for completion.

**When to use:** Any time the agent pipeline (minutes of LLM calls) would exceed Make.com's request timeout (~60s). Always appropriate here.

**Trade-offs:** Simple. No queue infrastructure needed at solo scale. The downside is no retry on failure — implement idempotency keys and a run-log table in Weaviate or a simple SQLite file so reruns don't duplicate signals.

**Example:**
```python
# api/routers/trigger.py
from fastapi import APIRouter, BackgroundTasks
from api.tasks.run_scout import run_scout_pipeline

router = APIRouter(prefix="/trigger")

@router.post("/scout", status_code=202)
async def trigger_scout(background_tasks: BackgroundTasks, date: str | None = None):
    run_date = date or today_iso()
    background_tasks.add_task(run_scout_pipeline, run_date)
    return {"status": "accepted", "date": run_date}
```

### Pattern 2: Headless Claude Agent Invocation

**What:** Each agent runs as a subprocess call to `claude -p` with a structured prompt, `--output-format json`, and `--allowedTools` scoped to what that agent needs. The Python caller parses the JSON result.

**When to use:** When the agent needs Claude Code's full agentic loop (file reads, Weaviate queries via Bash, MCP tool calls) but must be triggered programmatically rather than interactively.

**Trade-offs:** Robust — uses the same production agent loop. Subprocess overhead is negligible compared to LLM latency. The main cost is prompt + context window management: keep system prompts lean and pass structured JSON inputs, not freeform text.

**Example:**
```python
# agents/scout.py
import subprocess, json

def run_scout(date: str, paper_batch: list[dict]) -> dict:
    prompt = f"Score these ArXiv papers for date {date}: {json.dumps(paper_batch)}"
    result = subprocess.run(
        ["claude", "-p", prompt,
         "--model", "claude-haiku-4-5",
         "--output-format", "json",
         "--json-schema", SCOUT_OUTPUT_SCHEMA,
         "--allowedTools", "Bash",
         "--append-system-prompt", open("agents/prompts/scout_system.md").read()],
        capture_output=True, text=True, timeout=300
    )
    return json.loads(result.stdout)["structured_output"]
```

### Pattern 3: Sequential Agent Pipeline with Weaviate as Shared State

**What:** Agents run sequentially (Scout → Analyst → Translator → Briefing), each reading its inputs from Weaviate and writing outputs back. No direct agent-to-agent data passing via function arguments — Weaviate is the message bus.

**When to use:** Multi-stage pipelines where intermediate results must be queryable, filterable, and persistent. Makes each stage independently restartable.

**Trade-offs:** Resilient — if Analyst fails, Scout results survive and Analyst reruns from Weaviate. Slightly more latency than in-memory passing. Requires consistent Weaviate schema discipline (see db/schema.py as single source of truth).

**Data flow example:**
```
Scout writes:  Signal{ arxiv_id, title, abstract_embedding, score, tier, date }
Analyst reads: Signal collection filtered by (tier != ARCHIVE AND date == today)
Analyst writes: Signal.cluster_id, Signal.matched_patterns[] (update existing objects)
               PatternCandidate{ description, supporting_signal_ids, confidence }
Briefing reads: Signal filtered by (tier == BRIEF AND date == today)
Briefing writes: Briefing{ date, items[], recommendation_text, top_pattern_ids }
```

### Pattern 4: Feedback-Adjusted Scoring (not ML — rule-based weight shifting)

**What:** User ratings in the PWA (1–5 stars per signal) write to Weaviate Feedback collection. A nightly scoring-weight adjustment job reads feedback from the past N days and shifts pattern weights up or down. No model retraining — just weight coefficients.

**When to use:** When you have a solo user and need adaptation without ML infrastructure. Simple, auditable, reversible.

**Trade-offs:** Slower adaptation than gradient-based approaches. Sufficient for daily briefing cadence. Weight changes are logged so drift is visible. Starting weights are set manually during pattern bootstrapping.

---

## Data Flow

### Full Daily Pipeline Flow

```
[Make.com cron — 05:30]
    │
    ▼ HTTP POST /trigger/scout
[FastAPI — 202 Accepted]
    │ background task
    ▼
[Scout Agent — claude -p, Haiku]
    ├── Fetch ArXiv papers (past 24h)
    ├── Embed abstracts (Weaviate vectorizer or sentence-transformers)
    ├── Semantic search against Pattern library (nearVector query)
    ├── Score each paper (base score × pattern match weight × recency)
    ├── Apply three-tier gate (BRIEF/VAULT/ARCHIVE)
    └── Write Signal objects to Weaviate
    │
    ▼ (Scout complete — triggers Analyst via background task or cron)
[Analyst Agent — claude -p, Sonnet]
    ├── Query Weaviate: BRIEF + VAULT signals for today
    ├── Cluster by semantic similarity (nearVector groups)
    ├── Map clusters to existing patterns
    ├── Flag pattern candidates (new patterns emerging)
    └── Update Signal objects with cluster_id + matched_patterns
    │
    ▼ (parallel: Translator + Briefing)
[Translator Agent — claude -p, Sonnet]         [Briefing Agent — claude -p, Sonnet]
    ├── For each BRIEF signal:                     ├── Query BRIEF signals + clusters
    │   ├── Connect to vault knowledge             ├── Generate narrative briefing
    │   │   (Obsidian MCP: obs_search_notes)       ├── Add recommendations
    │   └── Deposit seed via Obsidian MCP          └── Write Briefing object to Weaviate
    └── Write Obsidian MCP deposit log
    │                                                    │
    └──────────────────┬──────────────────────────────────┘
                       ▼
[PWA serves briefing at /briefing/today]
    │
    ▼ User interaction (same day or next morning)
[Feedback — star rating per signal]
    │ POST /feedback/:signal_id
    ▼
[Weaviate Feedback collection updated]
    │ nightly job (Make.com cron)
    ▼
[Score weight adjustment — lib/scoring.py]
```

### Feedback Loop Architecture

```
[User rates signal in PWA]
        │
        ▼
Feedback{ signal_id, rating, date, pattern_ids[] }  → Weaviate
        │
        ▼ (nightly Make.com trigger → /trigger/calibrate)
[Calibration job]
        ├── Read last 30 days Feedback
        ├── Group by pattern_id
        ├── Compute avg rating per pattern (5-star = good signal, 1-star = noise)
        ├── Shift pattern.score_weight += delta (bounded: 0.5–2.0x)
        └── Write updated weights to Weaviate Pattern objects
```

### PWA Integration Points

```
Next.js frontend
    │
    ├── GET  /api/briefing/today       → FastAPI → Weaviate Briefing query
    ├── GET  /api/briefing/:date       → FastAPI → Weaviate Briefing query (history)
    ├── POST /api/feedback/:signal_id  → FastAPI → Weaviate Feedback write
    ├── GET  /api/patterns             → FastAPI → Weaviate Pattern query
    └── POST /api/patterns             → FastAPI → Weaviate Pattern create
```

---

## Weaviate Collection Design

Single-tenant (personal system). No multi-tenancy needed — use separate collections.

**Signal collection:**
```python
# Properties: arxiv_id (text), title (text), abstract (text),
#             source (text), date (date), tier (text: BRIEF|VAULT|ARCHIVE),
#             score (number), cluster_id (text), run_id (text)
# Vector: abstract embedding (default vectorizer)
# Cross-refs: hasPattern → Pattern (optional, added by Analyst)
```

**Pattern collection:**
```python
# Properties: name (text), description (text), score_weight (number),
#             created (date), last_matched (date), match_count (int)
# Vector: description embedding (for semantic search)
# No cross-refs — avoid bidirectional refs (Weaviate performance note)
```

**Hypothesis collection:**
```python
# Properties: statement (text), confidence (number 0-1),
#             status (text: active|confirmed|refuted),
#             created (date), last_updated (date)
# Vector: statement embedding
# Cross-refs: supportedBy → Signal (add sparingly — query by filter instead)
```

**Feedback collection:**
```python
# Properties: signal_id (text), rating (int 1-5), date (date),
#             pattern_ids (text[]), notes (text)
# No vector — not semantically searched, only filtered
```

**Briefing collection:**
```python
# Properties: date (date), brief_items (text[]), vault_items (text[]),
#             narrative (text), top_patterns (text[]), run_id (text)
# Vector: narrative embedding (for future similarity search across briefings)
```

**Design principle:** Avoid cross-references between high-volume collections (Signal ↔ Pattern). Instead, store `matched_pattern_ids` as a `text[]` property on Signal and filter/join in application code. Weaviate's cross-reference queries are slower at scale and add schema coupling.

---

## Anti-Patterns

### Anti-Pattern 1: Synchronous Make.com → Agent Call

**What people do:** Make.com HTTP module calls the VPS endpoint and waits for the full agent result (minutes of LLM processing).

**Why it's wrong:** Make.com HTTP requests time out at ~60 seconds. The Scout pipeline alone takes 2–5 minutes for a day's ArXiv batch. The scenario will fail silently or error out.

**Do this instead:** FastAPI returns 202 immediately. Make.com marks the step complete. Agent runs in a background task. Make.com optionally polls a `/status/:run_id` endpoint to confirm completion (optional for this solo system — a simple log file or Weaviate RunLog entry is sufficient).

### Anti-Pattern 2: Agents Calling Each Other Directly

**What people do:** Scout agent spawns the Analyst agent as a subprocess and passes results as function arguments or environment variables.

**Why it's wrong:** Creates tight coupling. If Analyst fails, Scout results are lost unless explicitly saved. Makes each agent non-restartable in isolation. Debugging requires tracing through nested subprocess chains.

**Do this instead:** Each agent reads inputs from Weaviate and writes outputs to Weaviate. The orchestration (when to run each stage) is handled by Make.com cron steps or a simple sequential task chain in FastAPI. The data layer is the contract, not direct process communication.

### Anti-Pattern 3: Auto-Editing Vault Knowledge Notes

**What people do:** The Translator agent tries to update or extend existing Knowledge notes in Obsidian, not just create new Seeds.

**Why it's wrong:** Mature Knowledge notes have carefully synthesized content. Auto-editing bypasses the human quality gate that SPARK is designed to enforce. Errors compound: a bad auto-edit to a cornerstone note corrupts downstream reasoning.

**Do this instead:** Translator deposits only into `01_seeds/` with `status: raw`. Franklin promotes manually. This preserves the Seeds → Knowledge flow and keeps human judgment on the maturity transition.

### Anti-Pattern 4: Storing Embeddings Twice

**What people do:** Store raw embeddings in both a Python dataclass and Weaviate; try to keep them in sync.

**Why it's wrong:** Weaviate IS the vector database. Its vectorizer handles embedding at write time. Maintaining a secondary copy creates consistency problems and wastes memory.

**Do this instead:** Pass raw text to Weaviate with a vectorizer configured. Let Weaviate own all embeddings. For semantic search, use `nearVector` or `nearText` queries directly against Weaviate.

### Anti-Pattern 5: One Monolithic Agent Prompt

**What people do:** Write a single large prompt that asks the agent to fetch, embed, score, cluster, translate, and format a briefing in one pass.

**Why it's wrong:** Context window fills with intermediate results. Error in any step contaminates the full output. Impossible to debug which stage failed. Cost is unpredictable.

**Do this instead:** Four specialized agents with narrow, verifiable outputs. Scout scores — that's all it does. Analyst clusters and maps. Each agent's output is JSON-structured and validated before the next agent runs.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Make.com | HTTP POST to FastAPI `/trigger/*`; receives 202 | Keep Make scenario logic minimal — trigger only |
| ArXiv API | REST poll in `lib/arxiv.py` (no auth needed) | Rate limit: 3 req/s; batch by date range |
| Weaviate | Python weaviate-client v4 (`weaviate.connect_to_local()`) | Already on VPS; use gRPC port 50051 for performance |
| Obsidian MCP | stdio MCP calls via `lib/obsidian.py` wrapper | mcp.ziksaka.com; only `obs_create_note` + `obs_search_notes` needed |
| Claude Agent SDK | Subprocess `claude -p` with `--output-format json` | Install `@anthropic-ai/claude-agent-sdk` on VPS; auth via ANTHROPIC_API_KEY env var |
| PWA (Next.js + FastAPI) | New routers added to existing FastAPI app | Mount `/briefing`, `/feedback`, `/patterns` routers |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Make.com → FastAPI | HTTP POST (fire-and-forget) | Payload: `{ "date": "YYYY-MM-DD", "run_id": "uuid" }` |
| FastAPI → Agent scripts | Python subprocess (BackgroundTasks) | JSON stdin/stdout; structured output schema enforced |
| Agent scripts → Weaviate | weaviate-client v4 (gRPC) | All reads/writes go through `db/client.py` singleton |
| Agent scripts → Obsidian | MCP stdio subprocess via `lib/obsidian.py` | Only Translator agent uses this |
| PWA frontend → FastAPI | HTTP REST (JSON) | Read-heavy; briefing is a GET with date param |
| Feedback → Scoring | Weaviate query in `lib/scoring.py` nightly job | Weights updated on Pattern objects in-place |

---

## Build Order (Phase Dependencies)

The dependency chain is strict. Each layer requires the one below it.

```
Phase 1: Foundation
├── Weaviate schema deployed (db/schema.py)
├── FastAPI trigger routes with 202 response (api/routers/trigger.py)
├── Make.com cron scenario wired to trigger endpoint
└── Claude Agent SDK installed + authenticated on VPS

Phase 2: Scout Pipeline (requires Phase 1)
├── ArXiv fetch (lib/arxiv.py)
├── Scout agent prompt + headless invocation
├── Signal scoring + three-tier gate (lib/scoring.py)
└── Signals written to Weaviate — verify with Weaviate console

Phase 3: Pattern Library (requires Phase 1; can run parallel to Phase 2)
├── Bootstrap initial patterns (scripts/bootstrap_patterns.py)
├── Pattern collection searchable via nearText
└── Score weights set (default: 1.0 for all patterns)

Phase 4: Analyst + Translator + Briefing Agents (requires Phase 2 + 3)
├── Analyst: cluster + map to patterns
├── Translator: seed deposit via Obsidian MCP
└── Briefing: generate daily brief + write to Weaviate

Phase 5: PWA Integration (requires Phase 4)
├── /briefing routes in FastAPI
├── Next.js briefing page
└── Feedback submission + Weaviate write

Phase 6: Feedback Loop + Calibration (requires Phase 5)
├── Weight adjustment job
├── Monthly eval test suite
└── PAR tracking operational
```

**Critical path:** VPS setup + Weaviate schema + FastAPI trigger endpoint must be done first. Everything else is blocked on these three. The Pattern library bootstrap can run in parallel with the Scout pipeline build, but both must complete before the Analyst agent is meaningful.

---

## Scaling Considerations

This is a single-user personal system. Scale is not a concern. The relevant concerns are cost, latency, and maintenance burden.

| Concern | Current Approach | When to Revisit |
|---------|-----------------|-----------------|
| LLM token cost | Haiku for Scout (high volume, cheap), Sonnet for Analyst/Translator/Briefing (low volume) | If source expansion (Phase 3+) adds >500 papers/day |
| Agent run time | Sequential pipeline ~10-15 min total; runs before Franklin wakes | If pipeline grows beyond 30 min, parallelize Scout batches |
| Weaviate memory | Single-tenant, <50k objects at full build-out; Docker default settings fine | Not a concern at solo scale |
| Make.com operations | 1 cron trigger + 1 calibration trigger daily = ~60 ops/month | Negligible; Franklin is a Make employee |
| FastAPI BackgroundTasks | Sufficient for 1 daily run; no queue needed | Switch to ARQ + Redis only if multiple concurrent runs needed |

---

## Sources

- [Claude Code headless / Agent SDK CLI](https://code.claude.com/docs/en/headless) — HIGH confidence, official docs
- [Claude Agent SDK TypeScript reference](https://platform.claude.com/docs/en/agent-sdk/typescript) — HIGH confidence, official docs
- [Claude Code: How it works (agentic loop)](https://code.claude.com/docs/en/how-claude-code-works) — HIGH confidence, official docs
- [Weaviate collection definitions](https://docs.weaviate.io/weaviate/starter-guides/managing-collections) — HIGH confidence, official docs
- [Weaviate cross-references](https://docs.weaviate.io/weaviate/manage-collections/cross-references) — HIGH confidence, official docs (with explicit caution to avoid where possible)
- [FastAPI BackgroundTasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) — HIGH confidence, official docs
- [Make.com webhooks](https://help.make.com/webhooks) — HIGH confidence, official docs
- [Agentic RAG survey (ArXiv 2501.09136)](https://arxiv.org/abs/2501.09136) — MEDIUM confidence, academic survey, patterns aligned with system design
- [Claude Agent SDK orchestration patterns (Skywork AI blog 2025)](https://skywork.ai/blog/claude-agent-sdk-best-practices-ai-agents-2025/) — LOW confidence, third-party blog; core patterns corroborated by official docs

---

*Architecture research for: Meridian — autonomous research intelligence pipeline*
*Researched: 2026-03-13*
