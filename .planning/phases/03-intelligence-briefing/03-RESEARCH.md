# Phase 3: Intelligence + Briefing - Research

**Researched:** 2026-03-15
**Domain:** LLM-driven signal clustering, structured narrative generation, FastAPI route extension, Weaviate write-back
**Confidence:** HIGH (all findings grounded in existing codebase; no speculative library choices)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Clustering Approach**
- Hybrid: pattern-anchored clustering first (group by shared matched_pattern_ids), then semantic similarity clustering for signals that don't anchor to a pattern
- Target 5-8 clusters per day
- Write cluster_id back to individual Signal objects in Weaviate (no separate Clusters collection)
- Singletons appear in briefing as "Notable singles" section

**Analyst Agent Design**
- Analyst receives full context per signal: title + abstract + score + matched patterns
- Analyst outputs structured JSON with cluster assignments AND 1-2 sentence theme summary per cluster
- Uses Sonnet (claude-sonnet-4-5) via invoke_claude()
- Clusters today's signals only, but queries last 7 days to annotate trends ("3rd paper on X this week")

**Briefing Narrative Design**
- Top 10 items per briefing (all BRIEF-tier clusters + notable singles, fill with top VAULT items)
- Strategic advisor tone — opinionated, forward-looking
- Opens with 3-sentence executive summary (landscape pulse)
- Per-item structure: what's happening → time horizon → recommended action
- Action type is tier-based: BRIEF gets strategic actions, VAULT gets read/investigate actions
- Single Sonnet call generates full narrative from Analyst output

**Pipeline Orchestration**
- Separate pipeline from Scout — Analyst+Briefing runs as its own function triggered after Scout completion
- Scout calls run_analyst_briefing_pipeline() at end of successful run
- Manual trigger endpoint: POST /briefing/generate (X-API-Key auth)
- If Analyst clustering fails, pipeline fails entirely — no degraded briefing

**PWA Briefing Viewer**
- Code lives in the existing PWA repo (Next.js + FastAPI), NOT in this meridian repo
- Meridian serves two API endpoints:
  - /briefing/today/narrative — pre-rendered narrative text
  - /briefing/today/data — structured JSON (clusters, signals, scores, patterns)
- Staleness warning: amber banner if pipeline hasn't run in >25 hours
- Briefing history: /briefing/today + sidebar showing last 7 briefings; past via /briefing/{date}
- Full stack delivery in this phase (backend agents + API + PWA route)

### Claude's Discretion
- Exact Analyst prompt wording and clustering instructions
- Briefing narrative formatting (markdown vs HTML vs plain text in items_json)
- Semantic clustering algorithm choice (Weaviate near_text vs custom embeddings)
- PWA component design, styling, and layout details
- API response pagination or caching strategy
- Error logging and monitoring approach for the Analyst+Briefing pipeline

### Deferred Ideas (OUT OF SCOPE)
- Briefing feedback mechanism (signal rating from PWA)
- Pattern momentum tracking (accelerating/decelerating patterns over time)
- Briefing delivery via other channels (email, Slack, Telegram)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INTEL-02 | Signal clustering and trend detection across accumulated signals (Analyst agent, Claude Sonnet) | Hybrid pattern-anchor + semantic clustering via Weaviate near_text; write cluster_id back via idempotent migration; trend annotations from 7-day query window |
| DELIV-01 | Morning briefing generated with top items, structured as: what's happening → time horizon → recommended action | Single Sonnet call generates narrative; Briefings collection already exists in schema; two API endpoints serve narrative + structured data to PWA |
</phase_requirements>

---

## Summary

Phase 3 builds on the Scout pipeline's scored Signals by adding two sequential agent steps: an Analyst that clusters today's signals into 5-8 topic groups, and a Briefing agent that turns those clusters into a structured narrative. The codebase already has all the primitives needed — `invoke_claude()`, `get_top_patterns()`, `get_client()`, `run_scout_pipeline()`, and the Briefings collection schema — so this phase is primarily assembly work, not new infrastructure.

The most critical design constraint is that cluster_id is written back to individual Signal objects via an idempotent schema migration (same pattern as `_migrate_signals_reasoning`). There is no separate Clusters collection. The Briefings collection stores both the pre-rendered narrative text (summary + items_json) and the structured data needed for the PWA's data endpoint. Two new FastAPI routes expose these to the PWA; the PWA code lives outside this repo.

The staleness detection logic (>25h since last pipeline run) requires a heartbeat file or timestamp readable by the API layer — the existing `heartbeat/scout.json` pattern can be extended or a new `heartbeat/briefing.json` created following the same shape.

**Primary recommendation:** Follow the `run_scout_pipeline()` shape exactly for `run_analyst_briefing_pipeline()`. Build Analyst and Briefing as two pure functions (cluster_signals, generate_briefing_narrative) called sequentially by the pipeline orchestrator. Write a single idempotent migration for cluster_id. Add two read routes and one trigger route under /briefing prefix.

---

## Standard Stack

### Core (all already present in project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| weaviate-client | installed | Read Signals, write cluster_id back, write Briefings | All collections already defined |
| fastapi | installed | New /briefing/* routes | Existing app pattern |
| pydantic | installed | Request/response models for briefing endpoints | Used throughout trigger.py |
| apscheduler | 3.x | No change needed — Scout already schedules via APScheduler | Briefing pipeline is triggered by Scout, not independently scheduled |

### No New Libraries Required

The phase requires zero new dependencies. Clustering is LLM-driven (invoke_claude with Sonnet) + Weaviate near_text (already used in get_top_patterns). No numpy, sklearn, or embedding libraries needed.

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── pipeline/
│   ├── scout.py          # existing — add call to run_analyst_briefing_pipeline() at end
│   ├── analyst.py        # NEW — cluster_signals(), trend_annotations()
│   └── briefing.py       # NEW — generate_briefing_narrative(), run_analyst_briefing_pipeline()
├── api/
│   └── routes/
│       ├── trigger.py    # existing
│       └── briefing.py   # NEW — /briefing/generate, /briefing/today/narrative, /briefing/today/data, /briefing/{date}/narrative, /briefing/{date}/data
├── db/
│   └── schema.py         # existing — add _migrate_signals_cluster_id()
└── runtime/
    └── claude_runner.py  # existing — reuse as-is, increase timeout for Sonnet calls
heartbeat/
├── scout.json            # existing
└── briefing.json         # NEW — same shape, written by run_analyst_briefing_pipeline()
```

### Pattern 1: Pipeline Orchestrator Shape

Follow `run_scout_pipeline()` exactly. The Analyst+Briefing pipeline should be:

```python
# src/pipeline/briefing.py
def run_analyst_briefing_pipeline() -> None:
    """Analyst + Briefing: cluster today's signals, generate narrative, write to Briefings."""
    client = get_client()
    try:
        signals = fetch_todays_signals(client)           # read BRIEF+VAULT from Signals
        history = fetch_recent_signals(client, days=7)   # for trend annotations
        clusters = cluster_signals(signals, history, client)  # Analyst agent
        write_cluster_ids(client, clusters)              # idempotent write-back
        narrative = generate_briefing_narrative(clusters)    # Briefing agent
        write_briefing(client, narrative, clusters)      # write to Briefings collection
        write_briefing_heartbeat(len(signals), len(clusters))
        logger.info(f"Briefing complete: {len(clusters)} clusters, {len(signals)} signals")
    finally:
        client.close()
```

Then in `scout.py`, add at the end of `run_scout_pipeline()` after `write_heartbeat(...)`:
```python
from src.pipeline.briefing import run_analyst_briefing_pipeline
run_analyst_briefing_pipeline()
```

### Pattern 2: Idempotent Schema Migration for cluster_id

```python
# src/db/schema.py — add to init_schema() call chain
def _migrate_signals_cluster_id(client: weaviate.WeaviateClient) -> None:
    """Idempotent migration: add cluster_id TEXT property to Signals if missing."""
    if not client.collections.exists("Signals"):
        return
    signals = client.collections.get("Signals")
    try:
        signals.config.add_property(Property(name="cluster_id", data_type=DataType.TEXT))
    except Exception:
        pass  # already exists
```

Add `_migrate_signals_cluster_id(client)` to `init_schema()`.

### Pattern 3: Analyst Agent — Structured JSON Output

The Analyst receives a single prompt containing all today's BRIEF+VAULT signals and outputs a JSON structure with cluster assignments. Use the same invoke_claude + json.loads + regex fallback pattern from score_paper():

```python
# Source: existing scout.py score_paper() pattern
ANALYST_PROMPT_TEMPLATE = """\
You are an intelligence analyst clustering AI research signals into thematic groups.

## Today's Signals
{signals_block}

## Recent Signal History (last 7 days — for trend annotations)
{history_block}

## Task
Group these signals into 5-8 thematic clusters. For signals sharing matched_pattern_ids,
anchor them in the same cluster. For remaining signals, use semantic similarity.

Respond ONLY with valid JSON:
{{
  "clusters": [
    {{
      "cluster_id": "<short-slug e.g. multi-agent-orchestration>",
      "theme_summary": "<1-2 sentence summary of what this cluster represents>",
      "signal_ids": ["<uuid>", ...],
      "matched_pattern_ids": ["<uuid>", ...],
      "trend_annotation": "<optional: e.g. 3rd paper on X this week, or null>"
    }}
  ],
  "singletons": ["<uuid>", ...]
}}
"""
```

**invoke_claude timeout:** Sonnet with a full day's signals (up to 50) will need a longer timeout. Use `timeout=300` (5 minutes). The existing default is 120s.

### Pattern 4: Briefing Route Design

```python
# src/api/routes/briefing.py
router = APIRouter(prefix="/briefing", tags=["briefing"])

@router.post("/generate", status_code=202)
async def generate_briefing(background_tasks: BackgroundTasks, _key=Security(verify_api_key)):
    background_tasks.add_task(run_analyst_briefing_pipeline)
    return {"status": "accepted"}

@router.get("/today/narrative")
async def today_narrative():
    # query Briefings collection for today's date, return summary + items_json as text
    ...

@router.get("/today/data")
async def today_data():
    # return structured JSON: clusters, signals, scores, patterns
    ...

@router.get("/{date}/narrative")
async def date_narrative(date: str):
    ...

@router.get("/{date}/data")
async def date_data(date: str):
    ...
```

Include in main.py alongside trigger_router.

### Pattern 5: Staleness Detection

The /briefing/today endpoints should check `heartbeat/briefing.json` and include a `stale` boolean + `last_run` timestamp in the response. The PWA renders the amber banner when `stale: true`.

```python
def get_briefing_staleness() -> dict:
    path = Path("heartbeat/briefing.json")
    if not path.exists():
        return {"stale": True, "last_run": None, "hours_since_run": None}
    data = json.loads(path.read_text())
    last_run = datetime.fromisoformat(data["last_run"])
    hours_ago = (datetime.now(timezone.utc) - last_run).total_seconds() / 3600
    return {"stale": hours_ago > 25, "last_run": data["last_run"], "hours_since_run": round(hours_ago, 1)}
```

### Anti-Patterns to Avoid

- **Separate Clusters collection:** Decided against — cluster_id lives on Signal objects only. Don't create a new Weaviate collection.
- **Streaming Sonnet response:** The invoke_claude() wrapper uses subprocess.run (blocking). Don't add streaming — keep it simple and testable.
- **Scheduling Briefing independently:** Briefing pipeline is triggered by Scout, not by APScheduler. Adding a second cron adds drift risk.
- **Multiple Sonnet calls for narrative:** One call generates the full briefing (executive summary + all items). Don't loop per-cluster.
- **Degraded briefing on Analyst failure:** Decided against — fail the whole pipeline so staleness warning surfaces clearly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Semantic clustering | Custom embedding + cosine similarity | Weaviate near_text (already used in get_top_patterns) | Text2vec transformer already running; near_text is one function call |
| JSON output enforcement | Custom parser | Existing regex fallback pattern from score_paper() | Already handles prose-wrapped responses |
| Cluster deduplication | Custom hash | cluster_id as string slug (e.g. "multi-agent-orchestration") | Simple, human-readable, Weaviate TEXT property |
| Auth on new routes | New auth system | Existing verify_api_key from src/api/auth.py | Identical pattern to trigger.py |
| Staleness timestamp | Database field | heartbeat/briefing.json (same as scout.json) | Filesystem heartbeat is already the established pattern |

---

## Common Pitfalls

### Pitfall 1: invoke_claude Timeout with Large Signal Set

**What goes wrong:** Sonnet analyzing 30-50 signals with 7-day history in a single prompt can exceed the 120s default timeout.
**Why it happens:** The default timeout in claude_runner.py is 120 seconds; Sonnet on a dense prompt can take 2-4 minutes.
**How to avoid:** Pass `timeout=300` explicitly for Analyst and Briefing calls.
**Warning signs:** `subprocess.TimeoutExpired` in logs.

### Pitfall 2: cluster_id Write-Back Race Condition

**What goes wrong:** If run_analyst_briefing_pipeline is called concurrently (manual trigger fires while Scout's call is in-flight), two pipelines write conflicting cluster_ids to the same Signal objects.
**Why it happens:** BackgroundTasks does not have a mutex.
**How to avoid:** Track pipeline state in heartbeat JSON (`"status": "running"`). Check at pipeline start; if already running, return early.
**Warning signs:** Duplicate Briefings entries for the same date.

### Pitfall 3: Weaviate Date Filter for "Today's Signals"

**What goes wrong:** Filtering Signals by published_date=today returns nothing because Scout fetches yesterday's ArXiv papers.
**Why it happens:** Scout uses `date.today() - timedelta(days=1)` as target_date.
**How to avoid:** Fetch signals by `generated_at` / `ingested_at` window (today's run), OR filter by published_date = yesterday. The cleanest approach: filter by Weaviate object creation timestamp or use a `pipeline_date` property. Simplest: filter published_date = yesterday (same logic as Scout's target_date).
**Warning signs:** Analyst receives empty signal list; briefing writes with item_count=0.

### Pitfall 4: Briefings Collection Date Deduplication

**What goes wrong:** Re-running briefing/generate creates a second Briefings object for the same date.
**Why it happens:** Briefings collection has no uniqueness constraint — unlike Signals where arxiv_id_exists() guards writes.
**How to avoid:** Before writing, query Briefings for today's date. If found, update (or delete + reinsert). Match the idempotent-by-lookup pattern from write_signal().
**Warning signs:** /briefing/today returns multiple results; PWA shows stale data.

### Pitfall 5: Sonnet JSON Schema Drift

**What goes wrong:** Sonnet outputs valid JSON but with different key names or nesting than expected (e.g. `"cluster_theme"` instead of `"theme_summary"`).
**Why it happens:** LLMs paraphrase schema keys under context pressure.
**How to avoid:** Include the JSON schema verbatim in the prompt (as done in SCORING_PROMPT_TEMPLATE). Add explicit validation after parsing: check required keys, raise ValueError on mismatch.
**Warning signs:** KeyError in cluster processing; briefing with empty themes.

---

## Code Examples

### Fetching Today's BRIEF+VAULT Signals

```python
# Source: adapted from scout.py arxiv_id_exists() pattern
from datetime import date, timedelta
from weaviate.classes.query import Filter

def fetch_todays_signals(client) -> list[dict]:
    """Fetch BRIEF and VAULT signals published yesterday (Scout's target date)."""
    target_date = date.today() - timedelta(days=1)
    signals_col = client.collections.get("Signals")
    response = signals_col.query.fetch_objects(
        filters=(
            Filter.by_property("tier").contains_any(["BRIEF", "VAULT"]) &
            Filter.by_property("published_date").greater_or_equal(
                target_date.isoformat() + "T00:00:00Z"
            )
        ),
        return_properties=["title", "abstract", "score", "tier",
                           "matched_pattern_ids", "reasoning"],
        limit=100,
    )
    return [{"uuid": str(obj.uuid), **obj.properties} for obj in response.objects]
```

### Writing cluster_id Back to a Signal

```python
# Source: Weaviate v4 client update pattern
def write_cluster_ids(client, clusters: dict) -> None:
    """Write cluster_id back to each Signal object. clusters: {uuid: cluster_id}"""
    signals_col = client.collections.get("Signals")
    for uuid, cluster_id in clusters.items():
        signals_col.data.update(uuid=uuid, properties={"cluster_id": cluster_id})
```

### Briefing Heartbeat (mirrors scout.py write_heartbeat)

```python
BRIEFING_HEARTBEAT_PATH = Path("heartbeat/briefing.json")

def write_briefing_heartbeat(signal_count: int, cluster_count: int) -> None:
    BRIEFING_HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BRIEFING_HEARTBEAT_PATH.write_text(json.dumps({
        "last_run": datetime.now(timezone.utc).isoformat(),
        "signals_processed": signal_count,
        "clusters_generated": cluster_count,
        "status": "ok",
    }))
```

### Querying the Most Recent Briefing for a Date

```python
def get_briefing_for_date(client, target_date: str) -> dict | None:
    """Return the Briefings object for target_date (ISO date string), or None."""
    briefings = client.collections.get("Briefings")
    response = briefings.query.fetch_objects(
        filters=Filter.by_property("date").greater_or_equal(
            target_date + "T00:00:00Z"
        ),
        limit=1,
    )
    if not response.objects:
        return None
    obj = response.objects[0]
    return {"uuid": str(obj.uuid), **obj.properties}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Separate clustering service (sklearn DBSCAN) | LLM-driven clustering via single Sonnet prompt | No new dependencies; LLM understands semantic meaning natively |
| Embedding-based similarity | Weaviate near_text (already running text2vec_transformers) | Zero additional infrastructure |
| Streaming Claude output | subprocess.run blocking (existing pattern) | Consistent with codebase; cleanly mockable in tests |

---

## Open Questions

1. **Weaviate object update method for cluster_id write-back**
   - What we know: Weaviate v4 client has `collection.data.update(uuid, properties)` for partial updates
   - What's unclear: Whether the existing weaviate-client version in this project supports `data.update()` vs requiring `data.replace()`
   - Recommendation: Wave 0 task should verify with a small integration test; fallback is delete+reinsert

2. **Briefings collection `date` property is DataType.DATE**
   - What we know: Weaviate DATE type requires RFC3339 format
   - What's unclear: Whether filtering by date prefix (YYYY-MM-DD) works correctly or requires full timestamp
   - Recommendation: Store as full ISO timestamp; filter with `.greater_or_equal` on date start + `.less_or_equal` on date end

3. **invoke_claude JSON output flag and schema enforcement**
   - STATE.md flags: "Verify `claude -p --json-schema` output enforcement behavior under edge cases"
   - What we know: invoke_claude uses `--output-format json` which wraps the result; the inner `result` string is the model's prose
   - What's unclear: Whether `--json-schema` flag (if it exists) enforces the response schema at the CLI level
   - Recommendation: Use the existing regex fallback + explicit key validation. Do not depend on CLI-level schema enforcement.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing, all 50 tests passing) |
| Config file | pytest.ini or pyproject.toml (check project root) |
| Quick run command | `pytest tests/test_analyst.py tests/test_briefing.py tests/test_briefing_routes.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INTEL-02 | cluster_signals() groups BRIEF+VAULT signals by pattern anchor | unit | `pytest tests/test_analyst.py::test_cluster_signals_pattern_anchor -x` | Wave 0 |
| INTEL-02 | Singletons are returned separately when no cluster match | unit | `pytest tests/test_analyst.py::test_cluster_signals_singletons -x` | Wave 0 |
| INTEL-02 | cluster_id is written back to Signal objects in Weaviate | unit | `pytest tests/test_analyst.py::test_write_cluster_ids -x` | Wave 0 |
| INTEL-02 | Trend annotations reference 7-day history | unit | `pytest tests/test_analyst.py::test_trend_annotations -x` | Wave 0 |
| DELIV-01 | generate_briefing_narrative() returns required structure | unit | `pytest tests/test_briefing.py::test_narrative_structure -x` | Wave 0 |
| DELIV-01 | run_analyst_briefing_pipeline() writes to Briefings collection | unit | `pytest tests/test_briefing.py::test_pipeline_writes_briefing -x` | Wave 0 |
| DELIV-01 | POST /briefing/generate returns 202 with valid key | unit | `pytest tests/test_briefing_routes.py::test_generate_trigger -x` | Wave 0 |
| DELIV-01 | GET /briefing/today/narrative returns narrative text + staleness | unit | `pytest tests/test_briefing_routes.py::test_today_narrative -x` | Wave 0 |
| DELIV-01 | GET /briefing/today/data returns structured JSON | unit | `pytest tests/test_briefing_routes.py::test_today_data -x` | Wave 0 |
| DELIV-01 | Staleness flag is True when heartbeat >25h old | unit | `pytest tests/test_briefing_routes.py::test_staleness_detection -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_analyst.py tests/test_briefing.py tests/test_briefing_routes.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_analyst.py` — covers INTEL-02 clustering and write-back
- [ ] `tests/test_briefing.py` — covers DELIV-01 pipeline and narrative generation
- [ ] `tests/test_briefing_routes.py` — covers DELIV-01 API endpoints and staleness

*(No framework gaps — pytest and conftest.py already exist with weaviate_client fixture)*

---

## Sources

### Primary (HIGH confidence)

- Existing codebase: `src/pipeline/scout.py` — pipeline shape, invoke_claude usage, pattern matching
- Existing codebase: `src/db/schema.py` — Briefings collection definition, migration pattern
- Existing codebase: `src/runtime/claude_runner.py` — invoke_claude signature and timeout default
- Existing codebase: `src/api/routes/trigger.py` — FastAPI route + BackgroundTasks + auth pattern
- Existing codebase: `src/api/main.py` — router registration pattern
- `.planning/phases/03-intelligence-briefing/03-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)

- Weaviate v4 Python client: `collection.data.update()` for partial property updates (standard v4 API)
- FastAPI BackgroundTasks: fire-and-forget pattern (well-established, used in existing trigger.py)

### Tertiary (LOW confidence — flag for validation)

- `claude -p --json-schema` flag behavior under edge cases — flagged in STATE.md, needs empirical verification
- Weaviate DATE filter behavior with YYYY-MM-DD prefix — needs Wave 0 integration test

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new libraries; all tools already in project
- Architecture: HIGH — directly mirrors existing scout.py and trigger.py patterns
- Pitfalls: HIGH — grounded in actual schema constraints and existing code behavior
- Open questions: LOW — three specific unknowns flagged for Wave 0 validation

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (stable codebase; no fast-moving external dependencies)
