# Phase 1: Foundation - Research

**Researched:** 2026-03-13
**Domain:** Weaviate schema, FastAPI webhook, Claude Code CLI headless, pattern library bootstrap
**Confidence:** HIGH (core stack verified via official docs and current web sources)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Pattern library domains:** Agentic Systems and LLMOps & Observability — Franklin's core expertise
- **Pattern count:** 15-20 seed patterns minimum
- **Pattern entry format:** Name + description + keywords + example signals + maturity level (emerging/established/declining) + related patterns + contrarian take
- **Authoring process:** Claude drafts from Franklin's vault knowledge notes (05_knowledge/), Franklin reviews before loading into Weaviate
- **Vault linking:** Bidirectional — each Weaviate pattern references vault source note path; vault notes get updated with Weaviate pattern ID
- **Make.com schedule:** Daily cron at 5-6 AM + manual webhook for on-demand runs
- **Make.com scope:** Dumb trigger only — HTTP POST to FastAPI endpoint, nothing else
- **Authentication:** Shared secret header (X-API-Key with static token)

### Claude's Discretion
- Weaviate collection schema design (property types, indexing strategy, embedding config)
- VPS Claude Code CLI installation and configuration approach
- FastAPI endpoint structure and background task implementation
- Embedding model deployment (nomic-embed-text-v1.5 per research recommendation)
- Weaviate RQ8 quantization configuration

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Weaviate collections deployed (signals, patterns, hypotheses, feedback, briefings) with locked schema | Weaviate Python v4 client collection creation API, DataType enum, RQ8 quantization config |
| INFRA-02 | Pattern library bootstrapped with 15-20 seed patterns in Weaviate with example signals | Pattern schema design, Python upsert API, vault-to-Weaviate bootstrap script pattern |
| INFRA-03 | Claude Code CLI installed and configured on VPS as agent runtime | Native installer via curl, ANTHROPIC_API_KEY env var for headless auth, `claude -p --output-format json` invocation |
| INFRA-04 | FastAPI pipeline orchestrator deployed with Make.com webhook trigger endpoint and shared-secret auth | FastAPI BackgroundTasks + 202 pattern, APIKeyHeader dependency, uvicorn deployment |
</phase_requirements>

---

## Summary

Phase 1 builds four co-equal foundational components: Weaviate schema, FastAPI trigger endpoint, Claude Code CLI runtime, and pattern library. None can be deferred because Phase 2 (Scout pipeline) depends on all four simultaneously. The project is greenfield — no existing code, no test infrastructure.

The primary technical risks are: (1) Weaviate Python client v4 API has breaking changes at v4.16 (renamed `vectorizer_config` to `vector_config`, renamed `Configure.NamedVectors` to `Configure.Vectors`) — pin to a specific version and use the new API throughout; (2) Claude Code CLI authentication on a headless VPS requires `ANTHROPIC_API_KEY` environment variable, not OAuth browser flow; (3) Make.com operation budget must be confirmed before finalizing trigger architecture.

**Primary recommendation:** Deploy Weaviate collections first (foundation of all other work), then FastAPI endpoint (validates the trigger chain), then Claude Code CLI (runtime readiness test), then pattern bootstrap (content that makes the system useful).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| weaviate-client | 4.9.x+ | Python client for Weaviate v4 API (gRPC) | Official client; v4 has type-safe collection API |
| fastapi | 0.115.x | HTTP framework for pipeline trigger endpoint | Already used in project PWA; async-native |
| uvicorn | 0.30.x | ASGI server for FastAPI | Standard production server for FastAPI |
| python-dotenv | 1.0.x | Load ANTHROPIC_API_KEY and X-API-Key from .env | Simple secret management for single-user VPS |
| httpx | 0.27.x | Async HTTP client for FastAPI background tasks | FastAPI-native; used for any outbound calls |
| pydantic | 2.x | Request/response schema validation | Bundled with FastAPI; type-safe models |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.x | Test framework for round-trip and smoke tests | All automated validation |
| pytest-asyncio | 0.23.x | Async test support for FastAPI endpoints | Testing async FastAPI routes |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI BackgroundTasks | Celery + Redis | Celery adds broker complexity; BackgroundTasks sufficient for single-user daily trigger |
| Static X-API-Key env var | OAuth / JWT | OAuth browser flow cannot run headless on VPS; X-API-Key is correct for single-user personal system |
| nomic-embed-text-v1.5 via Ollama | OpenAI text-embedding-3-small | Ollama keeps embeddings local/free; nomic-embed-text-v1.5 outperforms ada-002 on long context |

**Installation:**
```bash
pip install "weaviate-client>=4.9,<5" fastapi "uvicorn[standard]" python-dotenv httpx pydantic pytest pytest-asyncio
```

---

## Architecture Patterns

### Recommended Project Structure
```
meridian/
├── src/
│   ├── db/
│   │   ├── schema.py          # Collection definitions (DataType, Configure)
│   │   ├── client.py          # Weaviate connection factory
│   │   └── collections/       # Per-collection CRUD helpers
│   ├── api/
│   │   ├── main.py            # FastAPI app, lifespan, router mount
│   │   ├── auth.py            # APIKeyHeader dependency
│   │   └── routes/
│   │       └── trigger.py     # POST /pipeline/trigger → 202
│   ├── runtime/
│   │   └── claude_runner.py   # subprocess wrapper for `claude -p`
│   └── bootstrap/
│       └── seed_patterns.py   # One-shot pattern library loader
├── patterns/
│   └── seed/                  # JSON files, one per pattern (source of truth)
├── tests/
│   ├── conftest.py            # Weaviate test client, FastAPI TestClient
│   ├── test_schema.py         # Round-trip: insert + query 10 synthetic objects
│   ├── test_trigger.py        # POST /pipeline/trigger returns 202
│   └── test_claude_runner.py  # Smoke: claude -p returns parseable JSON
└── .env.example               # ANTHROPIC_API_KEY, WEAVIATE_URL, X_API_KEY
```

### Pattern 1: Weaviate Collection Creation (v4 API)
**What:** Define collections with typed properties, named vector config, and RQ quantization.
**When to use:** Schema initialization — run once at deploy time; skip if collection already exists.

```python
# Source: https://docs.weaviate.io/weaviate/manage-collections/collection-operations
import weaviate
from weaviate.classes.config import Configure, Property, DataType

def create_patterns_collection(client: weaviate.WeaviateClient) -> None:
    if client.collections.exists("Patterns"):
        return  # Schema locked — never drop/recreate in production

    client.collections.create(
        name="Patterns",
        description="Curated technology patterns scored against incoming signals",
        vector_config=Configure.Vectors.text2vec_ollama(
            api_endpoint="http://localhost:11434",
            model="nomic-embed-text",
        ),
        vector_index_config=Configure.VectorIndex.hnsw(
            quantizer=Configure.VectorIndex.Quantizer.rq(compression_level=8)
        ),
        properties=[
            Property(name="name",            data_type=DataType.TEXT),
            Property(name="description",     data_type=DataType.TEXT),
            Property(name="keywords",        data_type=DataType.TEXT_ARRAY),
            Property(name="maturity",        data_type=DataType.TEXT),  # emerging/established/declining
            Property(name="contrarian_take", data_type=DataType.TEXT),
            Property(name="related_patterns",data_type=DataType.TEXT_ARRAY),
            Property(name="vault_source",    data_type=DataType.TEXT),  # path in Obsidian vault
            Property(name="weaviate_id",     data_type=DataType.TEXT),  # back-filled after insert
        ],
    )
```

### Pattern 2: FastAPI Trigger Endpoint — 202 Accepted
**What:** Webhook endpoint that validates API key, enqueues background work, returns 202 immediately.
**When to use:** All asynchronous pipeline triggers.

```python
# Source: https://fastapi.tiangolo.com/tutorial/background-tasks/
from fastapi import APIRouter, BackgroundTasks, Security, HTTPException, status
from fastapi.security import APIKeyHeader
import os

router = APIRouter()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

async def verify_api_key(key: str = Security(api_key_header)) -> str:
    if key != os.environ["X_API_KEY"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return key

@router.post("/pipeline/trigger", status_code=202)
async def trigger_pipeline(
    background_tasks: BackgroundTasks,
    _key: str = Security(verify_api_key),
):
    background_tasks.add_task(run_scout_pipeline)
    return {"status": "accepted"}

async def run_scout_pipeline() -> None:
    # Phase 2 implementation — stub for Phase 1 smoke test
    pass
```

### Pattern 3: Claude Code CLI Subprocess Invocation
**What:** Call `claude -p` non-interactively from Python, parse JSON output.
**When to use:** Every agent invocation in the Scout pipeline.

```python
# Source: https://code.claude.com/docs/en/headless
import subprocess, json

def invoke_claude(prompt: str, model: str = "claude-sonnet-4-5") -> dict:
    result = subprocess.run(
        ["claude", "-p", "--output-format", "json", "--model", model],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI error: {result.stderr}")
    return json.loads(result.stdout)
    # Returns: {"result": "...", "model": "...", "usage": {...}, "cost_usd": ...}
```

### Pattern 4: Pattern Library Bootstrap (JSON → Weaviate)
**What:** Load hand-crafted JSON pattern files into Weaviate in a single idempotent pass.
**When to use:** One-shot seed load; re-runnable (upserts by name).

```python
# Source: Weaviate Python client v4 insert pattern
import json
from pathlib import Path

def seed_patterns(client, patterns_dir: str = "patterns/seed") -> None:
    collection = client.collections.get("Patterns")
    for path in Path(patterns_dir).glob("*.json"):
        data = json.loads(path.read_text())
        # Check by name to make idempotent
        existing = collection.query.fetch_objects(
            filters=collection.query.Filter.by_property("name").equal(data["name"]),
            limit=1,
        )
        if existing.objects:
            continue
        uuid = collection.data.insert(data)
        # Back-fill vault note with weaviate_id (Phase 1: log only, Phase 4: MCP write)
        print(f"Inserted pattern '{data['name']}' → {uuid}")
```

### Anti-Patterns to Avoid
- **Dropping and recreating collections to fix schema:** Weaviate schema is locked once data exists. Design properties correctly upfront. Add optional properties later with `collection.config.add_property()`.
- **Using `sudo npm install -g @anthropic-ai/claude-code`:** Permission issues and security risk. Use native installer or user-level npm prefix.
- **Storing X-API-Key in source code:** Always load from environment variable; use `.env` file locally, system env on VPS.
- **Running FastAPI `BackgroundTasks` for long-running multi-agent chains:** BackgroundTasks runs in the same process as the request handler. For Phase 2+ multi-agent pipelines, consider moving to `asyncio.create_task` with proper lifecycle management.
- **Using `Configure.NamedVectors` (deprecated in v4.16+):** Use `Configure.Vectors` instead.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vector similarity search | Custom cosine distance logic | Weaviate `nearVector` / `nearText` | HNSW + quantization; handles ANN, filtering, multi-vector |
| API key validation | Custom header parsing middleware | FastAPI `APIKeyHeader` + `Security()` dependency | OpenAPI schema integration, auto-error, dependency injection |
| Embedding generation | Custom Ollama HTTP calls | `Configure.Vectors.text2vec_ollama()` in Weaviate | Weaviate calls Ollama at index/query time automatically |
| CLI subprocess timeout/retry | Custom subprocess wrapper with retries | Standard `subprocess.run(timeout=N)` + caller retry | Claude CLI handles model-level retries; outer timeout sufficient |

---

## Common Pitfalls

### Pitfall 1: Weaviate v4.16 API Breaking Change
**What goes wrong:** Code using `vectorizer_config=` or `Configure.NamedVectors` throws AttributeError or unexpected behavior.
**Why it happens:** v4.16.0 renamed the API; old tutorials still show old syntax.
**How to avoid:** Always import from `weaviate.classes.config` and use `vector_config=Configure.Vectors.*`.
**Warning signs:** `AttributeError: module 'weaviate.classes.config' has no attribute 'NamedVectors'`

### Pitfall 2: Claude Code CLI Browser Auth on Headless VPS
**What goes wrong:** `claude auth login` attempts to open a browser; hangs or fails on headless server.
**Why it happens:** Default auth is OAuth browser flow.
**How to avoid:** Set `ANTHROPIC_API_KEY` environment variable before installing. Claude Code detects the env var and skips OAuth.
**Warning signs:** CLI hangs waiting for browser redirect; `xdg-open` errors.

### Pitfall 3: Weaviate Collection Name Casing
**What goes wrong:** Collection created as `patterns` is not found when queried as `Patterns`.
**Why it happens:** Weaviate collection names are case-sensitive and conventionally PascalCase.
**How to avoid:** Always use PascalCase for collection names: `Signals`, `Patterns`, `Hypotheses`, `Feedback`, `Briefings`.
**Warning signs:** `weaviate.exceptions.UnexpectedStatusCodeError: 404`

### Pitfall 4: Make.com Operation Budget
**What goes wrong:** Daily cron fires correctly for a week, then Make.com throttles or pauses the scenario.
**Why it happens:** Free/Starter Make.com tiers have monthly operation limits; one daily cron = ~30 ops/month minimum, but each HTTP module call counts separately.
**How to avoid:** Confirm account tier operation limit before finalizing scenario. Manual webhook trigger has no scheduled cost — consider making cron the fallback.
**Warning signs:** Make.com scenario shows "quota exceeded" or scenario auto-pauses.

### Pitfall 5: FastAPI BackgroundTask Outliving the Process
**What goes wrong:** VPS process restart kills an in-flight background task mid-pipeline.
**Why it happens:** BackgroundTasks run in-process; no persistence or restart recovery.
**How to avoid:** For Phase 1, this is acceptable (trigger endpoint is Phase 1 stub only). Document as a known limitation to address in Phase 2 when the real pipeline runs.

---

## Code Examples

### Weaviate Connection (v4 gRPC)
```python
# Source: https://docs.weaviate.io/weaviate/client-libraries/python
import weaviate

def get_client() -> weaviate.WeaviateClient:
    return weaviate.connect_to_local(
        host="localhost",   # or VPS IP
        port=8080,
        grpc_port=50051,
    )
```

### All Five Collection Definitions (summary)
| Collection | Key Properties | Notes |
|------------|---------------|-------|
| Signals | source_url, title, abstract, published_date, score, status | status: pending/scored/archived |
| Patterns | name, description, keywords[], maturity, contrarian_take, related_patterns[], vault_source | Core of scoring system |
| Hypotheses | statement, confidence, evidence_signal_ids[], created_date | v2 — create now, populate later |
| Feedback | signal_id, pattern_id, rating, comment, created_date | v2 — create now, populate later |
| Briefings | date, items[], summary, generated_at | items[] = JSON serialized signal summaries |

### Claude Code CLI JSON Output Structure
```json
{
  "result": "The assistant response text here",
  "model": "claude-sonnet-4-5",
  "usage": {
    "input_tokens": 123,
    "output_tokens": 456
  },
  "cost_usd": 0.0012
}
```
Access response text via `output["result"]`.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Configure.NamedVectors` | `Configure.Vectors` | Weaviate Python client v4.16 | Must use new API; old tutorials broken |
| `npm install -g @anthropic-ai/claude-code` | Native curl installer (no Node dependency) | Early 2026 | Simpler VPS install; npm path still works but discouraged |
| Weaviate v3 Python client (dict-based schema) | v4 client (type-safe, gRPC) | 2024 | Completely different API; v3 docs misleading |

**Deprecated/outdated:**
- `weaviate.Client()` (v3 constructor): replaced by `weaviate.connect_to_local()` / `connect_to_wcs()` in v4
- `client.schema.create_class()`: replaced by `client.collections.create()`
- `vectorizer_config=` parameter: replaced by `vector_config=` in v4.16+

---

## Open Questions

1. **Make.com operation budget**
   - What we know: Daily cron + manual webhook = low operation count
   - What's unclear: Franklin's exact account tier and monthly operation ceiling
   - Recommendation: Check Make.com account dashboard before finalizing trigger scenario. If budget is tight, make the VPS a self-hosted cron (systemd timer) calling the FastAPI endpoint directly — eliminates Make.com dependency for scheduling.

2. **Ollama availability on VPS**
   - What we know: Weaviate uses `text2vec-ollama` module requiring Ollama running locally
   - What's unclear: Whether Ollama is already installed and `nomic-embed-text` model pulled on the VPS
   - Recommendation: Verify with `ollama list` on VPS before schema deployment. If not present: `ollama pull nomic-embed-text:v1.5`.

3. **Weaviate Docker `text2vec-ollama` module enabled**
   - What we know: Weaviate modules must be explicitly enabled in Docker compose via `ENABLE_MODULES` env var
   - What's unclear: Current Weaviate Docker configuration on VPS
   - Recommendation: Confirm `text2vec-ollama` is in the `ENABLE_MODULES` list in the Docker compose file before creating collections.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23.x |
| Config file | `pytest.ini` — Wave 0 gap |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | Insert 10 synthetic objects into each of 5 collections, query back, verify count | integration | `pytest tests/test_schema.py -x` | ❌ Wave 0 |
| INFRA-01 | All 5 collections exist after schema init | smoke | `pytest tests/test_schema.py::test_collections_exist -x` | ❌ Wave 0 |
| INFRA-02 | At least 15 patterns queryable in Weaviate with non-null keywords and example signals | integration | `pytest tests/test_patterns.py -x` | ❌ Wave 0 |
| INFRA-03 | `claude -p --output-format json` returns parseable dict with `result` key | smoke | `pytest tests/test_claude_runner.py -x` | ❌ Wave 0 |
| INFRA-04 | POST /pipeline/trigger with valid X-API-Key returns 202 | unit | `pytest tests/test_trigger.py::test_trigger_returns_202 -x` | ❌ Wave 0 |
| INFRA-04 | POST /pipeline/trigger with invalid key returns 403 | unit | `pytest tests/test_trigger.py::test_trigger_rejects_bad_key -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q` (stop on first failure)
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `pytest.ini` — configure testpaths, asyncio_mode=auto
- [ ] `tests/conftest.py` — Weaviate test client fixture (connect to local), FastAPI TestClient fixture
- [ ] `tests/test_schema.py` — covers INFRA-01 round-trip
- [ ] `tests/test_patterns.py` — covers INFRA-02 pattern count and queryability
- [ ] `tests/test_claude_runner.py` — covers INFRA-03 CLI smoke test
- [ ] `tests/test_trigger.py` — covers INFRA-04 endpoint auth and 202
- [ ] Framework install: `pip install pytest pytest-asyncio httpx`

---

## Sources

### Primary (HIGH confidence)
- [Weaviate collection operations docs](https://docs.weaviate.io/weaviate/manage-collections/collection-operations) — create, exists, properties
- [Weaviate Python client v4 docs](https://docs.weaviate.io/weaviate/client-libraries/python) — connect_to_local, gRPC, v4.16 API changes
- [Weaviate RQ compression docs](https://docs.weaviate.io/weaviate/configuration/compression/rq-compression) — RQ8 quantization config
- [Weaviate Ollama embeddings docs](https://docs.weaviate.io/weaviate/model-providers/ollama/embeddings) — text2vec_ollama configuration
- [FastAPI background tasks docs](https://fastapi.tiangolo.com/tutorial/background-tasks/) — BackgroundTasks, 202 pattern
- [Claude Code headless docs](https://code.claude.com/docs/en/headless) — `-p` flag, `--output-format json`, subprocess pattern

### Secondary (MEDIUM confidence)
- [Weaviate v4.16 release blog](https://weaviate.io/blog/weaviate-1-35-release) — confirmed `Configure.Vectors` rename
- [FastAPI API key auth pattern](https://testdriven.io/tips/6840e037-4b8f-4354-a9af-6863fb1c69eb/) — APIKeyHeader + Security dependency
- [Claude Code VPS install guide](https://university.tenten.co/t/installing-claude-code-anthropics-official-cli-tool-on-a-remote-vps/2173) — ANTHROPIC_API_KEY headless auth

### Tertiary (LOW confidence — validate before use)
- Make.com operation limit specifics — verify against Franklin's actual account tier

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified via official docs, versions current as of 2026-03
- Architecture: HIGH — patterns derived from official FastAPI and Weaviate documentation
- Pitfalls: HIGH for items 1-3 (documented breaking changes and known issues); MEDIUM for items 4-5 (operational/deployment concerns)

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (30 days — Weaviate and FastAPI are stable; Claude Code CLI evolves faster, re-verify CLI flags if >30 days)
