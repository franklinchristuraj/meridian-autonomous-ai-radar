# Stack Research

**Domain:** Autonomous research intelligence system (daily scan → score → brief pipeline)
**Researched:** 2026-03-13
**Confidence:** MEDIUM-HIGH — Core decisions (Weaviate, ArXiv, Claude Agent SDK) verified against official sources. Make.com webhook patterns verified. Embedding model comparison MEDIUM (benchmark data from multiple sources, not single authoritative source).

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `weaviate-client` | 4.20.x | Vector DB client for signals, patterns, hypotheses, feedback | v4 GA uses gRPC for performance, collections-first API with strong typing. Already deployed on VPS — no alternative evaluation needed. |
| `claude-agent-sdk` | 0.1.48 | Agent runtime for Scout, Analyst, Translator agents | Official Anthropic SDK, spawns Claude Code CLI as subprocess. Supports MCP server connections (critical for Obsidian MCP integration). Persistent container mode supports long-running agent loops. |
| `anthropic` | latest | Direct Anthropic API access for Haiku/Sonnet calls | Used for scoring (Haiku) and analysis (Sonnet) outside the full agent loop — cheaper than spinning up full Agent SDK for simple structured outputs. |
| `arxiv` | 2.4.1 | ArXiv API wrapper | Official de-facto Python wrapper. Synchronous generator-based, handles rate limiting via `delay_seconds`. No auth required. Current version supports Python >=3.7, actively maintained. |
| `sentence-transformers` | 3.x | Local embedding generation | Self-hosted on VPS, no per-token cost, no API dependency. Uses `nomic-embed-text-v1.5` model (see Embedding Models section). Critical for VPS-local inference. |
| `apscheduler` | 3.10.x | In-process cron scheduling for FastAPI | Make.com is the external trigger layer, but APScheduler handles internal job coordination within the FastAPI service — lifespan context manager pattern prevents scheduler leak on restart. |
| `arize-phoenix` | latest OSS | LLM observability — trace Scout/Analyst/Translator calls | Self-hostable Docker image, OpenTelemetry-native, has first-class Claude Agent SDK support. Zero feature gates in OSS version. Required for Phase 5 cost monitoring. |

### Embedding Model

**Use: `nomic-embed-text-v1.5`** (via sentence-transformers, self-hosted)

Do not use `all-MiniLM-L6-v2`. It is outdated, has a 512-token context ceiling (research abstracts commonly exceed this), and benchmarks ~5-8% below current alternatives. `nomic-embed-text-v1.5` supports 8192-token context, runs locally via sentence-transformers, supports Matryoshka representation (768→256 flexible dimensions), and achieves 86.2% top-5 accuracy vs MiniLM's ~80%. Zero ongoing API cost.

Dimension to use in Weaviate: **768** (full precision for this scale — collection sizes will be thousands, not millions, so memory savings from Matryoshka truncation are unnecessary).

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | 0.27.x | Async HTTP client | Fetching from HuggingFace, GitHub, patents APIs in future source expansion phases. Prefer over `requests` for async FastAPI context. |
| `pydantic` | 2.x | Data validation and serialization | Signal schema validation before Weaviate ingestion. Use pydantic models as the single source of truth for collection schema shape. |
| `tenacity` | 8.x | Retry logic with exponential backoff | Wrap ArXiv API calls and Claude API calls. ArXiv requires 3s between requests — tenacity handles transient failures without manual sleep loops. |
| `python-dotenv` | 1.x | Environment variable management | Load `ANTHROPIC_API_KEY`, `WEAVIATE_URL`, `WEAVIATE_API_KEY` on VPS. Never hardcode credentials. |
| `opentelemetry-sdk` | latest | Telemetry instrumentation | Required to emit traces to Phoenix from both the Agent SDK and direct Anthropic calls. |
| `openinference-instrumentation-anthropic` | latest | Auto-instrumentation for Anthropic SDK | Captures Haiku/Sonnet call traces into Phoenix without manual span creation. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Docker Compose | Run Weaviate + Phoenix on VPS | Weaviate already deployed this way. Add Phoenix as a second service in same compose file. Use named volumes for persistence. |
| `uv` | Python package management | Faster than pip, lockfile support. Use `uv sync` for reproducible VPS deploys. Preferred over pip+venv for 2025 Python projects. |
| `pytest` + `pytest-asyncio` | Test suite | Unit test scoring logic and schema validation. Integration test Weaviate collection operations with a test collection (not prod). |
| Prometheus + Grafana | Weaviate metrics | Weaviate exposes a `/metrics` endpoint. Wire to Grafana for memory/recall monitoring on VPS. Lower priority than Phoenix but needed before scale. |

---

## Installation

```bash
# Create environment
uv init meridian
cd meridian
uv add weaviate-client==4.20.0
uv add claude-agent-sdk==0.1.48
uv add anthropic
uv add "arxiv==2.4.1"
uv add "sentence-transformers>=3.0"
uv add "apscheduler>=3.10"
uv add httpx pydantic tenacity python-dotenv

# Observability
uv add opentelemetry-sdk
uv add openinference-instrumentation-anthropic

# Dev
uv add --dev pytest pytest-asyncio
```

```bash
# Embedding model download (run once on VPS)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5')"
```

---

## Weaviate Collection Design

### Key Patterns

**Hybrid search requires explicit tokenization.** When creating a collection, set `tokenization=Tokenization.WORD` on text fields you want BM25-indexed. Without this, hybrid search silently falls back to vector-only.

**Alpha parameter.** Default `alpha=0.75` (leans vector). For research signal matching against a small pattern library, use `alpha=0.65` — this gives BM25 a stronger voice for exact term matching (model names, technique names like "RLHF", "LoRA" show up in both abstract and pattern description).

**Skip vectorization on metadata fields.** Set `skip_vectorization=True` on fields like `source`, `arxiv_id`, `published_date`, `score`. Only vectorize semantic content: `title`, `abstract`, `summary`.

**Quantization.** For VPS with limited RAM: enable RQ8 (rotational quantization, 8-bit) via `DEFAULT_QUANTIZATION=rq8` in docker-compose environment. Reduces memory ~75% with negligible recall loss. Do this from day one — changing quantization after ingestion requires re-indexing.

**Reranker.** Add a Cohere reranker (`rerank-english-v3.0`) for the briefing generation step when ranking top-N signals. This is a two-step fetch: vector+BM25 hybrid to get top 20, then cross-encoder rerank to get true top 5. Only needed in the Analyst agent, not the Scout scorer.

### Recommended Collections

```
Signals          — ArXiv papers + future sources, post-scoring
Patterns         — Franklin's pattern library (the matching targets)
Hypotheses       — Tracked hypotheses linked to signals
Feedback         — Daily ratings, used for scoring weight adjustment
```

---

## Make.com Integration Pattern

Make.com is the **external trigger layer only** — it fires HTTP webhooks to the FastAPI service. It does not contain agent logic.

**Pattern:**
1. Make.com scheduled scenario → POST to `https://[vps]/api/scout/trigger` with a shared secret header
2. FastAPI webhook endpoint validates secret, enqueues job
3. APScheduler (or direct background task) executes the Scout pipeline
4. Make.com receives 202 Accepted immediately — no timeout risk

**Why this split:** Make.com scenarios have a 40-second execution timeout per module and are not designed for long-running agent loops. Offload all execution to FastAPI + Agent SDK on VPS. Make.com is purely a reliable cron/trigger service.

**Alternative if VPS has reliable cron:** Use system cron (`crontab`) directly and skip Make.com for the Scout trigger. Make.com adds value for multi-step conditional triggers (e.g., "only run if it's a weekday") and for future webhook sources.

---

## Claude Agent SDK Deployment Pattern

The Agent SDK spawns Claude Code CLI as a subprocess. For VPS deployment:

1. Install Claude Code CLI globally on the VPS: `npm install -g @anthropic-ai/claude-code`
2. Set `ANTHROPIC_API_KEY` as environment variable (never in Dockerfile layer)
3. Use **persistent container mode** (not ephemeral per-task) — Meridian is a proactive background agent, not a user-interactive session
4. Pass MCP server configs (Obsidian MCP at `mcp.ziksaka.com`) via `ClaudeAgentOptions`
5. Run with `--network` access (unlike sandboxed user-facing agents, this system needs outbound HTTP for ArXiv + Weaviate + Obsidian MCP)

**Security note:** The VPS runs a personal system with no external users. Full network access is acceptable. For future multi-user expansion, re-evaluate with Docker `--network none` + proxy pattern.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `nomic-embed-text-v1.5` (local) | `text-embedding-3-small` (OpenAI API) | If VPS has <4GB RAM and can't load the model locally. API cost is $0.02/million tokens — acceptable for small daily batches but adds API dependency. |
| `weaviate-client` v4 | Qdrant or Pinecone | Qdrant if starting fresh with no VPS constraint. Pinecone if you want zero ops burden. But Weaviate is already deployed — do not change. |
| `claude-agent-sdk` | Direct `anthropic` API + custom tool loop | If agent capabilities (bash tools, MCP connections) are not needed. For Scout scoring, direct API is cheaper. Use direct API for Haiku scoring, Agent SDK for Analyst/Translator. |
| `apscheduler` | Celery + Redis | Celery only if task queue grows to multi-worker scale. Solo operator system with daily batch jobs — APScheduler in-process is sufficient and eliminates Redis dependency. |
| `arize-phoenix` | Langfuse | Langfuse is MEDIUM confidence alternative. Phoenix has explicit Claude Agent SDK instrumentation; Langfuse does not (as of research date). Use Phoenix. |
| `arxiv` Python package | Direct Atom/XML API polling | Use the package. It handles pagination, rate limiting, and retry. Raw XML parsing is unnecessary complexity. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `all-MiniLM-L6-v2` | 512-token context ceiling breaks for research abstracts. Outdated architecture, ~6% worse retrieval accuracy vs current models. Active HN discussion (Feb 2025) discourages new deployments. | `nomic-embed-text-v1.5` via sentence-transformers |
| Weaviate v3 Python client (`weaviate` package, not `weaviate-client`) | Deprecated. v3 uses REST-only, no gRPC, no collections API. v4 is the only supported path for new collections. | `weaviate-client>=4.20` |
| Make.com for agent logic | 40-second module timeout. No persistent state. Scenario logic is not Python — can't run sentence-transformers or Agent SDK natively. | FastAPI + Claude Agent SDK on VPS, triggered by Make.com webhook |
| n8n | Explicitly out of scope per PROJECT.md decision. Franklin has Make.com native expertise. | Make.com |
| Telegram delivery | Explicitly out of scope per PROJECT.md. No Telegram bot setup required. | PWA (Next.js) + Obsidian seed deposits |
| LangChain | Adds abstraction over Anthropic API that conflicts with Claude Agent SDK's own tool execution model. Unnecessary wrapper that obscures cost and debugging. | Direct `anthropic` SDK + `claude-agent-sdk` |
| `requests` library for async routes | Blocking in async FastAPI context causes thread pool starvation under load. | `httpx` with async client |

---

## Stack Patterns by Variant

**For Scout agent (ArXiv fetch + score):**
- Use direct `anthropic` API (Haiku model) for scoring — not Agent SDK
- Agent SDK overhead is unnecessary for a structured scoring task with no tool calls
- Pattern: fetch batch → embed locally → Weaviate hybrid search for pattern match → Haiku for score justification → store Signal

**For Analyst agent (cluster + map + propose):**
- Use `claude-agent-sdk` — needs Weaviate query tools and Obsidian MCP access
- MCP tool calls replace custom tool implementation
- Run on demand (post-Scout) not on a separate schedule

**For Translator agent (vault deposit):**
- Use `claude-agent-sdk` with Obsidian MCP connected
- Only deposits seeds — never modifies existing vault notes
- Rate-limit Obsidian MCP calls: max 3 seed deposits per run to prevent vault noise

**For Morning Briefing:**
- Use direct `anthropic` API (Sonnet) — structured JSON output → PWA
- No tool calls needed: just Weaviate query results → Sonnet prompt → formatted brief
- FastAPI endpoint returns brief JSON; Next.js PWA renders it

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `weaviate-client>=4.20` | Python >=3.10 | Do not use Python 3.9 or below. Weaviate v4 type hints require 3.10+. |
| `claude-agent-sdk==0.1.48` | Claude Code CLI (auto-included since ~0.1.40) | Claude Code CLI no longer needs separate npm install from v0.1.40+. Verify on VPS before assuming. |
| `sentence-transformers>=3.0` | PyTorch >=2.0 | Ensure VPS has PyTorch CPU build if no GPU. `pip install torch --index-url https://download.pytorch.org/whl/cpu` |
| `apscheduler>=3.10` | FastAPI lifespan API (>=0.93) | Use `lifespan` context manager pattern, not deprecated `@app.on_event("startup")`. APScheduler 4.x is in beta — use 3.10.x stable. |
| `arize-phoenix` OSS | Weaviate + FastAPI | Phoenix runs as a separate Docker service. No version conflict with application stack. |

---

## Sources

- [Weaviate Python Client v4 docs](https://docs.weaviate.io/weaviate/client-libraries/python) — v4.20.x confirmed current, collections API patterns, Python >=3.10 requirement — HIGH confidence
- [weaviate-client PyPI](https://pypi.org/project/weaviate-client/) — v4.20.0 released Feb 24, 2026 — HIGH confidence
- [Weaviate Hybrid Search docs](https://docs.weaviate.io/weaviate/search/hybrid) — alpha parameter, tokenization requirement, reranker integration — HIGH confidence
- [Weaviate Scalar/RQ Quantization docs](https://docs.weaviate.io/weaviate/configuration/compression/sq-compression) — RQ8 recommendation, DEFAULT_QUANTIZATION env var — HIGH confidence
- [arxiv PyPI](https://pypi.org/project/arxiv/) — v2.4.1 current, Python 3 only — HIGH confidence
- [arxiv.py GitHub](https://github.com/lukasschwab/arxiv.py) — rate limiting, delay_seconds pattern — HIGH confidence
- [claude-agent-sdk PyPI](https://pypi.org/project/claude-agent-sdk/) — v0.1.48 current — HIGH confidence
- [Anthropic Agent SDK hosting docs](https://platform.claude.com/docs/en/agent-sdk/hosting) — persistent vs ephemeral container patterns, VPS deployment — HIGH confidence
- [Anthropic secure deployment docs](https://platform.claude.com/docs/en/agent-sdk/secure-deployment) — network isolation, API key injection — HIGH confidence
- [Arize Phoenix GitHub](https://github.com/Arize-ai/phoenix) — self-hosted, Claude Agent SDK support confirmed — MEDIUM confidence (GitHub README, not formal docs)
- [nomic-embed-text-v1.5 HuggingFace](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) — 8192 context, Matryoshka support, sentence-transformers compatible — MEDIUM confidence
- [all-MiniLM-L6-v2 deprecation discussion](https://news.ycombinator.com/item?id=46081800) — community consensus against new deployments — LOW confidence (community thread, not official)
- [Make.com webhooks docs](https://help.make.com/webhooks) — webhook trigger patterns, instant vs scheduled — HIGH confidence
- [APScheduler + FastAPI patterns](https://rajansahu713.medium.com/implementing-background-job-scheduling-in-fastapi-with-apscheduler-6f5fdabf3186) — lifespan pattern — MEDIUM confidence (community article)

---

*Stack research for: Meridian — Autonomous Research Intelligence System*
*Researched: 2026-03-13*
