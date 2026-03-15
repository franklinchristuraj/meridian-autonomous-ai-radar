# Phase 4: Vault Integration - Research

**Researched:** 2026-03-15
**Domain:** Filesystem-based Obsidian seed note delivery, FastAPI extension, pipeline chaining
**Confidence:** HIGH

## Summary

Phase 4 extends the existing Scout → Analyst → Briefing pipeline chain with a Translator agent that writes seed notes directly to the Obsidian vault filesystem. All major design decisions are locked in CONTEXT.md: no MCP server, no REST plugin — direct `Path.write_text()` to `$OBSIDIAN_VAULT_PATH/01_seeds/`. The pattern is already established in `briefing.py` and `scout.py`; the Translator is another link in the chain, not a new architectural category.

The implementation has three distinct concerns: (1) a pipeline module (`src/pipeline/translator.py`) that fetches VAULT-tier signals, filters/caps to 3, renders seed note markdown, and writes files; (2) two FastAPI routes (`POST /vault/deposit`, `GET /vault/deposits`) following the existing briefing route shape; and (3) Briefing's `run_analyst_briefing_pipeline()` tail triggering the Translator, mirroring how Scout triggers Briefing.

The riskiest area is duplicate detection: scanning `01_seeds/` frontmatter to find existing `arxiv_url` values before writing. This requires reading potentially many `.md` files at runtime. The correct approach is a targeted glob + frontmatter parse (no external lib needed — YAML frontmatter is simple enough to parse with a regex or split on `---`).

**Primary recommendation:** Mirror briefing.py exactly — fetch → filter/rank → render → write → heartbeat — with filesystem write replacing Weaviate insert, and a lazy import wrapper in briefing.py for chain-trigger (same pattern as `_run_briefing_pipeline()` in scout.py).

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Obsidian Delivery Method**
- Direct filesystem write to the vault directory on the VPS — no MCP server, no REST API plugin
- Vault path configured via `OBSIDIAN_VAULT_PATH` environment variable
- Fail loud on startup if vault path or `01_seeds/` directory doesn't exist or isn't writable
- At runtime, Translator skips silently if vault becomes unavailable (log error, don't block pipeline)

**Seed Note Structure**
- Match existing vault seed template (`00_system/templates/seed_template.md`) for frontmatter convention
- Keep all template fields: `folder`, `type`, `created`, `status` ("raw"), `urgency`, `context` ("work"), `source` ("meridian"), `spark_stage` ("capture"), `tags`, `agent_context`
- Add Meridian-specific fields: `auto_deposit: true`, `signal_uuid`, `confidence`, `score`, `matched_patterns`, `arxiv_url`
- Tags: `[seed, auto-deposit]`
- Filename format: title slug only (e.g., `multi-agent-orchestration-framework.md`) — date lives in frontmatter
- Body: rich context — paper title (H1), full abstract, matched patterns with context, Analyst cluster context, recommended reading path

**Selection & Daily Cap**
- Filter: VAULT-tier signals with confidence >= 0.8 (no additional score floor)
- Rank: highest confidence first, take top 3
- Duplicate detection: scan existing `01_seeds/` frontmatter for matching `arxiv_url` before writing — skip if already deposited
- Daily cap enforced per pipeline run (count existing seeds deposited today)

**Pipeline Timing & Error Handling**
- Translator runs after Briefing completes — extends the chain: Scout → Analyst → Briefing → Translator
- Translator failure does not affect the pipeline — log error, skip deposit, try again next run
- No retry logic — if it fails, next day's run catches up
- Manual trigger endpoint: `POST /vault/deposit` (same X-API-Key auth pattern)
- Deposit listing endpoint: `GET /vault/deposits` — returns recent deposits (date, title, signal_uuid)

### Claude's Discretion
- Translator agent prompt design and model choice
- Rich context body formatting and section structure
- Slug generation algorithm for filenames
- Exact frontmatter field ordering
- Logging verbosity and format
- `GET /vault/deposits` response pagination or date filtering

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DELIV-02 | Auto-deposit VAULT-tier signals as seeds to Obsidian vault — confidence >= 0.8, max 3/day, `#auto-deposit` tag, full provenance in frontmatter, no existing note modification, queryable with back-link to originating Signal UUID in Weaviate | Filesystem write pattern documented; frontmatter schema mapped from seed_template.md + Meridian extensions; duplicate detection strategy confirmed; daily cap implementation pattern identified; API route shape established from briefing routes |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `pathlib` | stdlib | Filesystem reads/writes for vault notes | Already used throughout codebase (HEARTBEAT_PATH, etc.) |
| Python stdlib `re` | stdlib | Frontmatter parsing for duplicate detection, slug generation | No external YAML lib needed for simple frontmatter |
| `fastapi` | existing | API routes for trigger + listing endpoints | Project standard — all existing routes use FastAPI |
| `weaviate-client` | existing | Query VAULT-tier signals with confidence >= 0.8 | Project standard — all signal queries use existing get_client() |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-slugify` or stdlib `re` | stdlib preferred | Generate filename slugs from paper titles | Stdlib regex sufficient — `re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')` |
| `invoke_claude` (internal) | existing | Translator agent calls for rich body generation | Use for Claude Sonnet body generation if prompt-based approach; optional — body can be template-rendered without LLM |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib frontmatter parse | `python-frontmatter` lib | External dep not worth it — YAML frontmatter here is flat key-value, regex split on `---` is sufficient |
| Direct filesystem write | Obsidian MCP / REST plugin | Explicitly rejected in locked decisions — filesystem is simpler and sufficient |
| LLM body generation | Template rendering | Discretionary — LLM adds richer prose but adds latency/cost; template is reliable fallback |

**Installation:** No new dependencies required. All needed libraries are already in the project.

## Architecture Patterns

### Recommended Project Structure
```
src/
├── pipeline/
│   ├── translator.py        # new — Translator pipeline module
│   └── briefing.py          # existing — add _run_translator_pipeline() tail call
├── api/
│   └── routes/
│       └── vault.py         # new — /vault/deposit and /vault/deposits routes
└── api/
    └── main.py              # existing — register vault router
tests/
└── test_translator.py       # new — TDD unit tests for translator module
    test_vault_routes.py     # new — route tests
heartbeat/
└── translator.json          # new — heartbeat file (same pattern as scout.json, briefing.json)
```

### Pattern 1: Pipeline Module Shape (mirrors briefing.py exactly)

**What:** fetch → filter/rank/cap → render → write → heartbeat
**When to use:** Every pipeline stage in this project follows this shape

```python
# src/pipeline/translator.py — follows briefing.py shape
def run_translator_pipeline() -> None:
    """Orchestrate Translator: fetch VAULT signals → filter → render → write seeds."""
    client = get_client()
    try:
        signals = fetch_vault_signals(client)          # VAULT-tier, confidence >= 0.8
        candidates = rank_and_cap(signals, max_n=3)    # highest confidence first
        seeds_path = get_vault_seeds_path()             # $OBSIDIAN_VAULT_PATH/01_seeds/
        deposited = 0
        for signal in candidates:
            if _arxiv_url_deposited(seeds_path, signal["source_url"]):
                logger.info(f"Skipping duplicate: {signal['source_url']}")
                continue
            if deposited >= 3:
                break
            content = render_seed_note(signal)
            filename = slugify(signal["title"]) + ".md"
            (seeds_path / filename).write_text(content)
            deposited += 1
            logger.info(f"Deposited seed: {filename}")
        write_translator_heartbeat(deposited)
    except Exception as e:
        logger.error(f"Translator pipeline failed: {e}")
        # Do NOT re-raise — failure must not block pipeline
    finally:
        client.close()
```

### Pattern 2: Chain Trigger in briefing.py (mirrors scout.py's `_run_briefing_pipeline`)

**What:** Lazy import wrapper at tail of `run_analyst_briefing_pipeline()`, same pattern as scout.py's `_run_briefing_pipeline()`
**When to use:** Whenever chaining a new pipeline stage to avoid circular imports at module level

```python
# Add to src/pipeline/briefing.py
def _run_translator_pipeline() -> None:
    """Delegate to run_translator_pipeline (lazy import avoids circular deps)."""
    from src.pipeline.translator import run_translator_pipeline
    run_translator_pipeline()

# At tail of run_analyst_briefing_pipeline(), after write_briefing_heartbeat():
_run_translator_pipeline()
```

### Pattern 3: Vault Startup Validation

**What:** Check `OBSIDIAN_VAULT_PATH` env var + `01_seeds/` exists + writable at startup
**When to use:** Called from `get_vault_seeds_path()` — fail loud on startup, skip silently at runtime

```python
import os
from pathlib import Path

def get_vault_seeds_path() -> Path:
    """Return Path to vault 01_seeds/ directory. Raises on startup misconfiguration."""
    vault_root = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault_root:
        raise EnvironmentError("OBSIDIAN_VAULT_PATH not set")
    seeds = Path(vault_root) / "01_seeds"
    if not seeds.exists():
        raise FileNotFoundError(f"Vault seeds directory not found: {seeds}")
    if not os.access(seeds, os.W_OK):
        raise PermissionError(f"Vault seeds directory not writable: {seeds}")
    return seeds
```

### Pattern 4: Duplicate Detection via Frontmatter Scan

**What:** Scan `01_seeds/*.md` files, parse `arxiv_url:` from frontmatter, return set for O(1) lookup
**When to use:** Called once per pipeline run before deposit loop

```python
import re
from pathlib import Path

def _load_deposited_urls(seeds_path: Path) -> set[str]:
    """Return set of arxiv_urls already present in 01_seeds/ frontmatter."""
    urls = set()
    for md_file in seeds_path.glob("*.md"):
        try:
            text = md_file.read_text()
            # Extract frontmatter block between first two ---
            fm_match = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
            if fm_match:
                url_match = re.search(r'^arxiv_url:\s*(.+)$', fm_match.group(1), re.MULTILINE)
                if url_match:
                    urls.add(url_match.group(1).strip())
        except Exception:
            continue  # Corrupt file — skip, don't fail
    return urls
```

### Pattern 5: Seed Note Frontmatter Rendering

**What:** Render YAML frontmatter + markdown body matching vault template + Meridian extensions
**When to use:** `render_seed_note(signal)` — produces the full `.md` file content

```python
# Frontmatter fields: all from seed_template.md + Meridian extensions
# seed_template.md fields: folder, type, created, status, urgency, context, source,
#                           spark_stage, tags, processed_date, promoted_to, agent_context
# Meridian additions: auto_deposit, signal_uuid, confidence, score,
#                     matched_patterns, arxiv_url

def render_seed_note(signal: dict, agent_summary: str = "") -> str:
    title = signal.get("title", "Untitled")
    today = date.today().isoformat()
    frontmatter = f"""---
folder: "01_seeds"
type: "seed"
created: {today}
status: "raw"
urgency: "low"
context: "work"
source: "meridian"
spark_stage: "capture"
tags: [seed, auto-deposit]
processed_date: ""
promoted_to: ""
agent_context: "Auto-deposited VAULT signal from Meridian — {agent_summary}"
auto_deposit: true
signal_uuid: "{signal.get('uuid', '')}"
confidence: {signal.get('confidence', 0.0)}
score: {signal.get('score', 0.0)}
matched_patterns: {signal.get('matched_pattern_ids', [])}
arxiv_url: "{signal.get('source_url', '')}"
---"""
    body = f"# {title}\n\n{signal.get('abstract', '')}\n"
    return frontmatter + "\n\n" + body
```

### Pattern 6: API Routes Shape (mirrors briefing routes)

**What:** `POST /vault/deposit` triggers pipeline via BackgroundTasks; `GET /vault/deposits` returns recent deposits scanned from filesystem
**When to use:** New `src/api/routes/vault.py` — register in main.py

```python
# src/api/routes/vault.py
router = APIRouter(prefix="/vault", tags=["vault"])

@router.post("/deposit", status_code=202)
async def trigger_deposit(
    background_tasks: BackgroundTasks,
    _key: str = Security(verify_api_key),
) -> dict:
    background_tasks.add_task(run_translator_pipeline)
    return {"status": "accepted"}

@router.get("/deposits")
async def list_deposits() -> dict:
    # Scan 01_seeds/ for auto_deposit: true files, return recent entries
    ...
```

### Anti-Patterns to Avoid

- **Raising exceptions from `run_translator_pipeline()`:** Translator failure MUST be swallowed after logging — re-raising would propagate to BackgroundTasks and surface as 500 in logs for the Briefing task.
- **Writing seeds without checking daily cap first:** The cap is 3 per run — count both already-deposited-today AND newly-written-this-run.
- **Modifying existing seed files:** Duplicate detection skips writing — never overwrite. Read-only scan, write-only new files.
- **Calling `get_vault_seeds_path()` inside the error-swallowing block:** Vault misconfiguration (missing env var) should raise loud at trigger time / startup, not be silently swallowed.
- **Using VAULT-tier `score` as confidence:** CONTEXT.md specifies filtering by `confidence >= 0.8`. The Signals schema has both `score` (numeric 1-10 from Haiku) and `confidence` (from Analyst clustering). The filter is on `confidence`, not `score`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML frontmatter serialization | Custom YAML writer | Simple f-string template (flat key-value only) | Frontmatter is flat — no nested YAML; f-string is readable and testable |
| Signal querying | Custom Weaviate query builder | Extend `fetch_todays_signals()` pattern from analyst.py | Filter shape already established: `Filter.by_property("tier").equal("VAULT")` chained with confidence filter |
| File collision avoidance | UUID suffix logic | Duplicate detection on `arxiv_url` frontmatter | arxiv_url is the canonical dedup key, not filename |
| Async file I/O | asyncio file writes | Synchronous `Path.write_text()` | Pipeline runs in BackgroundTasks — blocking I/O is fine; no event loop contention |

## Common Pitfalls

### Pitfall 1: Confidence Field Missing on Older Signals
**What goes wrong:** Signals ingested before the Analyst clustering phase may not have a `confidence` property set — `.get("confidence")` returns `None`, which fails `>= 0.8` comparison.
**Why it happens:** Schema migrations are idempotent but don't backfill values — older signals have `confidence=None`.
**How to avoid:** Use `float(signal.get("confidence") or 0.0) >= 0.8` in the filter.
**Warning signs:** Zero candidates selected despite VAULT-tier signals existing in Weaviate.

### Pitfall 2: Daily Cap Double-Counting
**What goes wrong:** Daily cap counts "seeds deposited today" by scanning `01_seeds/` for `created: {today}` frontmatter — but this scan runs BEFORE writing, so newly-deposited seeds in the same run aren't counted yet.
**Why it happens:** Scan is a snapshot; runtime counter isn't incremented.
**How to avoid:** Track `deposited` as an in-memory counter incremented after each successful write; check `deposited < 3` in the loop guard, not just the pre-scan count.

### Pitfall 3: Slug Collisions
**What goes wrong:** Two papers with similar titles produce the same slug, second write overwrites the first.
**Why it happens:** Slug generation strips punctuation and spaces; titles like "On X" and "On X: a study" may collide.
**How to avoid:** Check `(seeds_path / filename).exists()` before writing. If collision, append `-2`, `-3`, etc. Or: arxiv_url duplicate check prevents same-paper collision; different-paper collision on filename is extremely rare but check `.exists()` anyway.

### Pitfall 4: Vault Path Not Set in BackgroundTasks Context
**What goes wrong:** `OBSIDIAN_VAULT_PATH` env var is present at server start but `get_vault_seeds_path()` is called inside the BackgroundTask worker thread where env may not be inherited in some deployment setups.
**Why it happens:** Non-issue in standard subprocess/uvicorn deployments, but worth noting.
**How to avoid:** Read `os.environ.get("OBSIDIAN_VAULT_PATH")` at function call time (not at module import time). Current pattern of reading in `get_vault_seeds_path()` is correct.

### Pitfall 5: Frontmatter Parse Fails on Notes with Multiple `---` Blocks
**What goes wrong:** Some vault notes have code blocks containing `---`; regex `re.match(r'^---\n(.*?)\n---', text, re.DOTALL)` incorrectly captures too much.
**Why it happens:** Greedy vs non-greedy; first `---` delimiter pair is correct but only if non-greedy.
**How to avoid:** Use non-greedy `.*?` (already shown above). Only parse frontmatter — stop at second `---`.

## Code Examples

### Fetch VAULT signals with confidence filter
```python
# Source: extends fetch_todays_signals() pattern from src/pipeline/analyst.py
from weaviate.classes.query import Filter
from datetime import date

def fetch_vault_signals(client) -> list[dict]:
    """Fetch today's VAULT-tier signals with confidence >= 0.8."""
    signals_col = client.collections.get("Signals")
    today_str = date.today().isoformat()
    response = signals_col.query.fetch_objects(
        filters=(
            Filter.by_property("tier").equal("VAULT")
            & Filter.by_property("published_date").greater_or_equal(f"{today_str}T00:00:00Z")
        ),
        return_properties=["title", "abstract", "source_url", "score", "confidence",
                           "matched_pattern_ids", "cluster_id"],
        limit=50,
    )
    return [
        {**obj.properties, "uuid": str(obj.uuid)}
        for obj in response.objects
        if float(obj.properties.get("confidence") or 0.0) >= 0.8
    ]
```

### Rank and cap candidates
```python
# Source: extends _sort_and_cap_items() pattern from src/pipeline/briefing.py
def rank_and_cap(signals: list[dict], max_n: int = 3) -> list[dict]:
    """Sort by confidence descending, take top max_n."""
    return sorted(
        signals,
        key=lambda s: float(s.get("confidence") or 0.0),
        reverse=True,
    )[:max_n]
```

### Heartbeat write (same shape as briefing.py)
```python
TRANSLATOR_HEARTBEAT_PATH = Path("heartbeat/translator.json")

def write_translator_heartbeat(deposited: int) -> None:
    TRANSLATOR_HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRANSLATOR_HEARTBEAT_PATH.write_text(json.dumps({
        "last_run": datetime.now(timezone.utc).isoformat(),
        "seeds_deposited": deposited,
        "status": "ok",
    }))
```

### Register vault router in main.py
```python
# src/api/main.py — add alongside briefing router
from src.api.routes.vault import router as vault_router
app.include_router(vault_router)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Obsidian MCP server for vault writes | Direct filesystem write | Locked decision Phase 4 context | Simpler — no MCP dependency, no Obsidian running required on VPS |
| Manual vault seeding | Automated Translator pipeline | Phase 4 | DELIV-02 closes the last open v1 requirement |

**Note on `confidence` field:** The Signals schema as of Phase 3 does NOT have a `confidence` property defined in `schema.py`. The Analyst clustering assigns `confidence` scores conceptually but this may be stored differently. This requires verification — see Open Questions below.

## Open Questions

1. **Does the Signals collection have a `confidence` property?**
   - What we know: `schema.py` shows Signals has `score`, `tier`, `status`, `matched_pattern_ids`, `reasoning`, `cluster_id` — no explicit `confidence` property. The Analyst module stores cluster confidence, but it is unclear if it is written back to individual Signal objects.
   - What's unclear: Is confidence stored on the Signal object, or only on the cluster? Does CONTEXT.md's "confidence >= 0.8" refer to the Signal's score mapped differently, or a property that needs a schema migration?
   - Recommendation: The planner MUST verify `src/pipeline/analyst.py` `write_cluster_ids()` to see what is written back to Signals. If confidence is not on Signals, Plan 04-01 (Wave 0) must add a `_migrate_signals_confidence` idempotent migration and update how Analyst writes confidence back.

2. **`GET /vault/deposits` — filesystem scan vs. heartbeat record**
   - What we know: The listing endpoint must return recent deposits (date, title, signal_uuid). This data can be read by scanning `01_seeds/` for `auto_deposit: true` + `created:` date in frontmatter, or by maintaining a separate deposits log file.
   - What's unclear: Whether pagination/date filtering is needed (left to Claude's discretion).
   - Recommendation: Scan `01_seeds/` frontmatter at request time — no extra state needed, consistent with filesystem-as-source-of-truth principle. Return last 30 days by default.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing — `tests/` directory, `conftest.py`) |
| Config file | `pytest.ini` or `pyproject.toml` (check project root) |
| Quick run command | `pytest tests/test_translator.py tests/test_vault_routes.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DELIV-02 | `fetch_vault_signals` returns only VAULT-tier signals with confidence >= 0.8 | unit | `pytest tests/test_translator.py::test_fetch_vault_signals_filters_confidence -x` | Wave 0 |
| DELIV-02 | `rank_and_cap` returns at most 3, sorted by confidence desc | unit | `pytest tests/test_translator.py::test_rank_and_cap -x` | Wave 0 |
| DELIV-02 | Duplicate detection skips signals whose arxiv_url appears in existing seeds | unit | `pytest tests/test_translator.py::test_duplicate_detection_skips -x` | Wave 0 |
| DELIV-02 | `render_seed_note` includes all required frontmatter fields (auto_deposit, signal_uuid, arxiv_url, tags with auto-deposit) | unit | `pytest tests/test_translator.py::test_render_seed_note_frontmatter -x` | Wave 0 |
| DELIV-02 | `run_translator_pipeline` does not raise even if vault path is unavailable at runtime | unit | `pytest tests/test_translator.py::test_pipeline_swallows_runtime_errors -x` | Wave 0 |
| DELIV-02 | `run_translator_pipeline` raises `EnvironmentError` / `FileNotFoundError` at startup if vault path misconfigured | unit | `pytest tests/test_translator.py::test_vault_path_validation -x` | Wave 0 |
| DELIV-02 | Daily cap: no more than 3 seeds written per run regardless of qualifying signals | unit | `pytest tests/test_translator.py::test_daily_cap_enforced -x` | Wave 0 |
| DELIV-02 | `POST /vault/deposit` returns 202, requires X-API-Key | unit | `pytest tests/test_vault_routes.py::test_deposit_trigger_accepted -x` | Wave 0 |
| DELIV-02 | `GET /vault/deposits` returns deposits list | unit | `pytest tests/test_vault_routes.py::test_list_deposits -x` | Wave 0 |
| DELIV-02 | Briefing pipeline tail-calls Translator (chain wiring) | unit | `pytest tests/test_briefing.py::test_briefing_triggers_translator -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_translator.py tests/test_vault_routes.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_translator.py` — covers all DELIV-02 pipeline unit tests
- [ ] `tests/test_vault_routes.py` — covers vault API route tests
- [ ] No framework install needed — pytest already present

## Sources

### Primary (HIGH confidence)
- `src/pipeline/briefing.py` — Pipeline shape, `_sort_and_cap_items`, chain trigger pattern
- `src/pipeline/scout.py` — `_run_briefing_pipeline()` lazy import wrapper pattern, heartbeat pattern
- `src/api/routes/briefing.py` — Route shape: BackgroundTasks trigger, Security(verify_api_key), router prefix
- `src/api/auth.py` — X-API-Key middleware pattern
- `src/db/schema.py` — Signals schema properties (confirmed: no `confidence` property — see Open Questions)
- `00_system/templates/seed_template.md` — Canonical seed frontmatter fields

### Secondary (MEDIUM confidence)
- `CONTEXT.md` — All locked decisions; authoritative for this phase
- `STATE.md` — Accumulated decisions, pipeline chain decisions documented

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all patterns are from existing codebase
- Architecture: HIGH — Translator is a direct mirror of briefing.py; confirmed from source
- Pitfalls: HIGH for filesystem/cap pitfalls (derived from code); MEDIUM for confidence field question (requires verification of analyst.py)

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (stable — no fast-moving external dependencies)
