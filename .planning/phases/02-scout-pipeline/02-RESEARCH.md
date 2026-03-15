# Phase 2: Scout Pipeline - Research

**Researched:** 2026-03-15
**Domain:** ArXiv ingestion, Haiku scoring, Weaviate nearVector, background pipeline
**Confidence:** HIGH (core stack already in codebase; arxiv.py and Weaviate v4 APIs verified)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Fetch papers from cs.AI, cs.CL, cs.CV, cs.LG, cs.MA, cs.SD — previous day only (24-hour window)
- If a run is missed, next run catches the gap naturally (ArXiv API supports date range queries)
- Keyword pre-filtering before any Haiku calls: match paper title + abstract against pattern library keywords
- Keywords sourced dynamically from the Patterns collection in Weaviate (no static list)
- As patterns are added/updated, the keyword filter auto-expands
- Soft cap of ~50 papers per day after keyword filtering — rank by keyword density, take top 50
- Deduplication by arxiv_id before writing to Weaviate
- Pattern selection per paper: embed title+abstract, run nearVector against Patterns collection, take top 5 closest matches
- Individual Haiku calls — one paper + its top-5 patterns per call (not batched)
- Haiku returns structured output: relevance score (1-10), matched pattern names, and 1-2 sentence reasoning
- Relevance framing: pattern alignment + novelty — high score means the paper directly advances or challenges an existing pattern with novel evidence/approach
- Pattern contrarian_take fields inform the scoring prompt to help calibrate novelty detection
- Reasoning is stored alongside the score to aid Franklin's calibration during the 5-briefing validation gate
- BRIEF >= 7.0 / VAULT 5.0-6.9 / ARCHIVE < 5.0
- Tier assignment written to Signal.tier field; matched pattern IDs written to Signal.matched_pattern_ids
- Make.com → FastAPI POST /pipeline/trigger with X-API-Key auth → BackgroundTasks → run_scout_pipeline()

### Claude's Discretion
- Exact scoring prompt wording and JSON schema for Haiku output
- ArXiv API client implementation (arxiv 2.4.1 library per requirements)
- Heartbeat file format and location
- Error handling and retry strategy for Haiku calls and ArXiv API
- How reasoning text is stored (new Signal property or embedded in existing field)
- Keyword density ranking algorithm for the soft cap

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INGEST-01 | Daily ArXiv fetch from cs.AI, cs.CL, cs.CV, cs.LG, cs.MA, cs.SD via arxiv 2.4.1 | arxiv.py Search class with `cat:` query + `submittedDate` range filter; Result fields: title, summary (abstract), entry_id, published |
| INGEST-02 | LLM relevance scoring (Claude Haiku) of each signal against pattern library (1-10 scale) | Existing `invoke_claude()` with model override; structured JSON prompt schema; per-paper individual calls |
| INTEL-01 | Semantic source-to-pattern matching via Weaviate nearVector search | Weaviate v4 collection.query.near_text() or near_vector() against Patterns collection; returns top-N by vector distance |
</phase_requirements>

---

## Summary

Phase 2 implements the daily Scout pipeline: fetch yesterday's ArXiv papers from 6 categories, keyword-filter against the live pattern library, score survivors with Claude Haiku using nearVector-matched patterns as context, assign tiers, and write scored Signal objects to Weaviate. The pipeline runs inside the existing `run_scout_pipeline()` stub in `trigger.py`, called from FastAPI BackgroundTasks.

All infrastructure exists from Phase 1. The work is purely logic: one new module (`src/pipeline/scout.py` or similar), extensions to the Signal schema for `reasoning` storage, and a heartbeat file writer. The main technical risks are (1) the arxiv.py query syntax for multi-category + date range, (2) Weaviate nearVector requiring the text2vec-transformers vectorizer to be running, and (3) `invoke_claude()` needing JSON-schema enforcement for Haiku output parsing.

**Primary recommendation:** Build the pipeline as a single `run_scout_pipeline()` function decomposed into clearly named helper functions (fetch → keyword_filter → score → write). Each helper is independently testable with mocks matching the established pattern in `test_claude_runner.py`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| arxiv | 2.4.1 (per REQUIREMENTS.md) | ArXiv API client | Official Python wrapper; locked by project |
| weaviate-client | >=4.9,<5 (in requirements.txt) | Vector DB reads/writes | Already in project; v4 gRPC client |
| fastapi | >=0.115,<1 | HTTP + BackgroundTasks | Already in project |
| python-dotenv | >=1.0,<2 | Env config | Already in project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest + unittest.mock | >=8,<9 (already installed) | Unit tests with subprocess/Weaviate mocks | All new modules |
| pathlib | stdlib | Heartbeat file writing | Simple file I/O |
| datetime | stdlib | Date range calculation for ArXiv query | Previous-day window |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| arxiv 2.4.1 | feedparser on ArXiv Atom feed | arxiv.py is cleaner API; locked decision |
| individual Haiku calls | batch prompt | Individual calls are simpler, debuggable, and aligned with locked decision |

**Installation (new dependency only):**
```bash
pip install "arxiv>=2.4,<3"
```
Add to requirements.txt: `arxiv>=2.4,<3`

---

## Architecture Patterns

### Recommended Project Structure
```
src/
├── pipeline/
│   ├── __init__.py
│   └── scout.py          # All Scout logic: fetch, filter, score, write
├── api/routes/
│   └── trigger.py        # Replace stub with: from src.pipeline.scout import run_scout_pipeline
tests/
└── test_scout.py         # Unit tests for each scout helper
heartbeat/
└── scout.json            # Written on each successful run
```

### Pattern 1: ArXiv Multi-Category + Date Range Query
**What:** Combine multiple `cat:` filters with OR and a `submittedDate` range using the raw query string passed to `arxiv.Search`.
**When to use:** Daily fetch of yesterday's papers across 6 categories.

```python
# Source: arxiv API user manual (info.arxiv.org/help/api/user-manual.html)
# and lukasschwab/arxiv.py GitHub README
import arxiv
from datetime import date, timedelta

def build_arxiv_query(target_date: date) -> str:
    date_str = target_date.strftime("%Y%m%d")
    categories = ["cs.AI", "cs.CL", "cs.CV", "cs.LG", "cs.MA", "cs.SD"]
    cat_filter = " OR ".join(f"cat:{c}" for c in categories)
    # submittedDate wildcard: all submissions on the target date
    return f"({cat_filter}) AND submittedDate:{date_str}*"

def fetch_arxiv_papers(target_date: date | None = None) -> list[arxiv.Result]:
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    client = arxiv.Client()
    search = arxiv.Search(
        query=build_arxiv_query(target_date),
        max_results=500,  # fetch wide, then keyword-filter down to 50
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    return list(client.results(search))
```

**arxiv.Result fields used:**
- `result.entry_id` → extract arxiv_id (e.g. `"2401.12345v1"` → strip to `"2401.12345"`)
- `result.title` → Signal.title
- `result.summary` → Signal.abstract (summary IS the abstract in arxiv.py)
- `result.published` → Signal.published_date
- `result.primary_category` → for logging/debug

### Pattern 2: Weaviate nearVector Pattern Matching
**What:** Embed paper title+abstract via Weaviate's built-in vectorizer, then run nearVector (or near_text) against the Patterns collection to find the 5 closest patterns.
**When to use:** Per-paper, before Haiku scoring call.

```python
# Source: docs.weaviate.io/weaviate/search/similarity
# Weaviate v4 Python client collection query API
import weaviate
from weaviate.classes.query import MetadataQuery

def get_top_patterns(
    client: weaviate.WeaviateClient,
    title: str,
    abstract: str,
    top_n: int = 5,
) -> list[dict]:
    """Return top_n patterns most similar to the paper's title+abstract."""
    patterns = client.collections.get("Patterns")
    text_to_match = f"{title}\n\n{abstract}"
    response = patterns.query.near_text(
        query=text_to_match,
        limit=top_n,
        return_metadata=MetadataQuery(distance=True),
    )
    return [
        {
            "name": o.properties.get("name"),
            "description": o.properties.get("description"),
            "contrarian_take": o.properties.get("contrarian_take"),
            "keywords": o.properties.get("keywords", []),
            "uuid": str(o.uuid),
            "distance": o.metadata.distance,
        }
        for o in response.objects
    ]
```

**Note:** `near_text` works because the Patterns collection uses `text2vec_transformers` vectorizer. The vectorizer must be running on the VPS (confirmed from Phase 1 Weaviate setup). No separate embedding step needed.

### Pattern 3: Haiku Scoring Call
**What:** Reuse `invoke_claude()` with model override and a structured prompt that returns JSON.
**When to use:** Per paper that passes keyword filter, with its top-5 matched patterns as context.

```python
# Source: existing src/runtime/claude_runner.py pattern
import json
from src.runtime.claude_runner import invoke_claude

SCORING_PROMPT_TEMPLATE = """\
You are scoring an AI research paper for relevance to a forward intelligence pattern library.

## Paper
Title: {title}
Abstract: {abstract}

## Top Matched Patterns
{patterns_block}

## Task
Score this paper's relevance on a scale of 1-10.
- 8-10: Directly advances or challenges a pattern with novel evidence/approach
- 5-7: Relevant to a pattern but incremental or confirmatory
- 1-4: Tangentially related or rehashes well-known work

Consider the contrarian_take fields when assessing novelty.

Respond ONLY with valid JSON matching this exact schema:
{{
  "score": <number 1-10, one decimal place allowed>,
  "matched_pattern_names": [<list of pattern names that influenced your score>],
  "reasoning": "<1-2 sentences explaining why this score>"
}}
"""

def score_paper(title: str, abstract: str, patterns: list[dict]) -> dict:
    patterns_block = "\n\n".join(
        f"Pattern: {p['name']}\nDescription: {p['description']}\n"
        f"Contrarian Take: {p.get('contrarian_take', 'N/A')}"
        for p in patterns
    )
    prompt = SCORING_PROMPT_TEMPLATE.format(
        title=title,
        abstract=abstract,
        patterns_block=patterns_block,
    )
    raw = invoke_claude(prompt, model="claude-haiku-4-5")
    # invoke_claude returns {"result": "<text>", ...}
    return json.loads(raw["result"])
```

### Pattern 4: Keyword Pre-filter
**What:** Fetch all pattern keywords from Weaviate, then score each paper by keyword hits in title+abstract. Keep top 50 by density.

```python
def fetch_pattern_keywords(client: weaviate.WeaviateClient) -> list[str]:
    patterns = client.collections.get("Patterns")
    response = patterns.query.fetch_objects(return_properties=["keywords"])
    keywords = []
    for o in response.objects:
        keywords.extend(o.properties.get("keywords", []))
    return list(set(kw.lower() for kw in keywords))

def keyword_density(text: str, keywords: list[str]) -> int:
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw in text_lower)

def keyword_filter(papers: list, keywords: list[str], cap: int = 50) -> list:
    scored = [
        (p, keyword_density(p.title + " " + p.summary, keywords))
        for p in papers
    ]
    scored = [(p, s) for p, s in scored if s > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:cap]]
```

### Pattern 5: Signal Write with Deduplication
**What:** Check arxiv_id uniqueness before insert using Weaviate filter query.

```python
from weaviate.classes.query import Filter

def arxiv_id_exists(client: weaviate.WeaviateClient, arxiv_id: str) -> bool:
    signals = client.collections.get("Signals")
    response = signals.query.fetch_objects(
        filters=Filter.by_property("arxiv_id").equal(arxiv_id),
        limit=1,
    )
    return len(response.objects) > 0

def write_signal(client: weaviate.WeaviateClient, data: dict) -> None:
    if arxiv_id_exists(client, data["arxiv_id"]):
        return  # idempotent — skip duplicate
    signals = client.collections.get("Signals")
    signals.data.insert(data)
```

### Pattern 6: Heartbeat File
**What:** Write a JSON heartbeat on successful pipeline completion.

```python
import json
from pathlib import Path
from datetime import datetime, timezone

HEARTBEAT_PATH = Path("heartbeat/scout.json")

def write_heartbeat(paper_count: int, scored_count: int) -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_PATH.write_text(json.dumps({
        "last_run": datetime.now(timezone.utc).isoformat(),
        "papers_fetched": paper_count,
        "papers_scored": scored_count,
        "status": "ok",
    }))
```

### Anti-Patterns to Avoid
- **Calling Haiku on all fetched papers:** Always keyword-filter first. 500 Haiku calls/day is ~$0.05; 50 is ~$0.005. More importantly, low-relevance papers inflate ARCHIVE tier and pollute the calibration signal.
- **Static keyword list:** Keywords must come from Weaviate Patterns collection at runtime. Static lists drift as patterns evolve.
- **Batching Haiku prompts:** The locked decision is one paper + its top-5 patterns per call. Batching would require a different response schema and is out of scope.
- **Fetching vectors explicitly:** Use `near_text` not `near_vector` for pattern matching — the vectorizer handles embedding automatically. No need to generate embeddings externally.
- **Suppressing `invoke_claude` errors:** A failed Haiku call should log and skip the paper, not crash the pipeline. The heartbeat must still be written if the overall run succeeds.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ArXiv HTTP pagination | Custom HTTP + XML parser | `arxiv.Client().results()` | Handles rate-limiting, pagination, XML parsing automatically |
| Vector similarity search | Cosine similarity in Python | Weaviate nearVector/nearText | Approximate nearest-neighbor at scale; already deployed |
| Text vectorization | Call an embedding API | Weaviate text2vec_transformers (built-in) | Vectorizer runs alongside Weaviate on VPS; zero extra cost |
| Structured JSON from LLM | Regex parsing of Haiku output | JSON prompt schema + `json.loads(raw["result"])` | Haiku is reliable with explicit schema in prompt |

---

## Common Pitfalls

### Pitfall 1: arxiv_id Format Inconsistency
**What goes wrong:** `result.entry_id` returns a full URL like `http://arxiv.org/abs/2401.12345v1`. Storing this raw causes deduplication misses when the same paper appears with a different version suffix.
**Why it happens:** The arxiv.py library exposes the full URL, not a clean ID.
**How to avoid:** Normalize on ingest: `arxiv_id = result.entry_id.split("/abs/")[-1].split("v")[0]`
**Warning signs:** Duplicate Signal objects with the same title but different arxiv_id values.

### Pitfall 2: submittedDate vs. lastUpdatedDate Confusion
**What goes wrong:** ArXiv papers are often revised; a paper from 2023 revised yesterday appears in `lastUpdatedDate` queries for "yesterday" but is not a new paper.
**Why it happens:** ArXiv's `submittedDate` and `lastUpdatedDate` are different fields.
**How to avoid:** Use `submittedDate:{YYYYMMDD}*` in the query (already in the pattern above). This fetches only originally submitted papers from that date.
**Warning signs:** Signal dates appearing older than yesterday's date.

### Pitfall 3: Haiku JSON Parse Failure
**What goes wrong:** `json.loads(raw["result"])` raises `JSONDecodeError` when Haiku includes prose before/after the JSON object.
**Why it happens:** Haiku occasionally adds preamble text even with strict prompts.
**How to avoid:** Add a JSON extraction fallback: search for `{...}` block in the result string using `re.search(r'\{.*\}', raw["result"], re.DOTALL)` before parsing. Log the raw output on failure.
**Warning signs:** JSONDecodeError exceptions in scout logs.

### Pitfall 4: Weaviate Connection Not Closed
**What goes wrong:** Each pipeline run leaks a gRPC connection if `client.close()` is not called in a `finally` block.
**Why it happens:** BackgroundTasks runs `run_scout_pipeline()` without an async context manager.
**How to avoid:** Always use try/finally in `run_scout_pipeline()`:
```python
client = get_client()
try:
    # ... pipeline logic
finally:
    client.close()
```

### Pitfall 5: Signal Schema Missing `reasoning` Field
**What goes wrong:** The current `Signals` collection schema (Phase 1) has no `reasoning` field. Writing reasoning as a property fails silently or raises a Weaviate schema error.
**Why it happens:** The reasoning requirement was added in Phase 2 context; schema was defined in Phase 1.
**How to avoid:** Wave 0 task must add `reasoning` property to Signals collection. Use idempotent schema migration: check if property exists before adding. Alternatively store as JSON string in a new `scoring_metadata` TEXT field.

### Pitfall 6: ArXiv Rate Limiting
**What goes wrong:** `arxiv.Client().results()` iterates lazily; fetching 500 results rapidly triggers ArXiv's rate limiter (3 requests/second limit).
**Why it happens:** The default `arxiv.Client` has a delay_seconds parameter defaulting to 3s, but high page_size requests can still hit limits.
**How to avoid:** Use `arxiv.Client(num_retries=3, page_size=100)` — smaller pages with retries. Daily batch at ~06:00 UTC is off-peak for ArXiv.

---

## Code Examples

### Full Pipeline Skeleton
```python
# src/pipeline/scout.py
import logging
from datetime import date, timedelta
from pathlib import Path

from src.db.client import get_client

logger = logging.getLogger(__name__)

def run_scout_pipeline() -> None:
    """Daily Scout: fetch, filter, score, write. Called by FastAPI BackgroundTasks."""
    target_date = date.today() - timedelta(days=1)
    client = get_client()
    try:
        papers = fetch_arxiv_papers(target_date)
        keywords = fetch_pattern_keywords(client)
        filtered = keyword_filter(papers, keywords, cap=50)
        logger.info(f"Scout: {len(papers)} fetched, {len(filtered)} after keyword filter")

        scored = 0
        for paper in filtered:
            arxiv_id = paper.entry_id.split("/abs/")[-1].split("v")[0]
            if arxiv_id_exists(client, arxiv_id):
                continue
            try:
                patterns = get_top_patterns(client, paper.title, paper.summary)
                result = score_paper(paper.title, paper.summary, patterns)
                score = float(result["score"])
                tier = "BRIEF" if score >= 7.0 else "VAULT" if score >= 5.0 else "ARCHIVE"
                write_signal(client, {
                    "arxiv_id": arxiv_id,
                    "title": paper.title,
                    "abstract": paper.summary,
                    "source_url": paper.entry_id,
                    "published_date": paper.published.isoformat(),
                    "score": score,
                    "tier": tier,
                    "status": "scored",
                    "matched_pattern_ids": [p["uuid"] for p in patterns],
                    "reasoning": result.get("reasoning", ""),
                })
                scored += 1
            except Exception as e:
                logger.error(f"Scout: failed to score {arxiv_id}: {e}")
                continue

        write_heartbeat(len(papers), scored)
        logger.info(f"Scout complete: {scored} signals written")
    finally:
        client.close()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Weaviate v3 Python client (`.query.get()`) | v4 collection API (`.collections.get("Name").query`) | v4 GA 2024 | v4 is in requirements.txt; all queries use new API |
| `search.results()` (old arxiv.py) | `client.results(search)` with `arxiv.Client()` | arxiv.py 2.x | Must instantiate Client separately from Search |

---

## Open Questions

1. **`reasoning` field storage**
   - What we know: Signals schema has no `reasoning` property today
   - What's unclear: Should it be a separate TEXT property, or packed into a JSON `scoring_metadata` blob?
   - Recommendation: Add `reasoning` as a dedicated TEXT property — readable for Franklin's 5-briefing review, searchable in future

2. **Vectorizer availability on VPS**
   - What we know: Weaviate deployed with `text2vec_transformers` config in Phase 1
   - What's unclear: Whether the transformer model container is running and responding (integration test required)
   - Recommendation: Wave 0 smoke test: call `near_text` against Patterns collection with a test query; fail loudly if vectorizer is down

3. **Make.com cron timing**
   - What we know: Make.com trigger is already wired to the endpoint
   - What's unclear: Exact UTC time of trigger (ArXiv publishes ~00:00 ET / 05:00 UTC; trigger should be after 06:00 UTC)
   - Recommendation: Document expected cron time in heartbeat; treat as operator config

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | none detected — uses pytest discovery |
| Quick run command | `pytest tests/test_scout.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-01 | `fetch_arxiv_papers()` returns Result list for a date | unit (mock arxiv.Client) | `pytest tests/test_scout.py::test_fetch_arxiv_papers -x` | Wave 0 |
| INGEST-01 | arxiv_id is normalized (no URL, no version suffix) | unit | `pytest tests/test_scout.py::test_arxiv_id_normalization -x` | Wave 0 |
| INGEST-01 | keyword_filter returns <= 50 papers ranked by density | unit | `pytest tests/test_scout.py::test_keyword_filter_cap -x` | Wave 0 |
| INGEST-02 | `score_paper()` parses Haiku JSON response correctly | unit (mock invoke_claude) | `pytest tests/test_scout.py::test_score_paper -x` | Wave 0 |
| INGEST-02 | `score_paper()` handles JSONDecodeError gracefully | unit | `pytest tests/test_scout.py::test_score_paper_bad_json -x` | Wave 0 |
| INGEST-02 | Tier assignment: score 7.5 → BRIEF, 6.0 → VAULT, 3.0 → ARCHIVE | unit | `pytest tests/test_scout.py::test_tier_assignment -x` | Wave 0 |
| INTEL-01 | `get_top_patterns()` returns top 5 with name/uuid/distance | unit (mock Weaviate collection) | `pytest tests/test_scout.py::test_get_top_patterns -x` | Wave 0 |
| INTEL-01 | Deduplication: paper with existing arxiv_id is skipped | unit (mock Weaviate filter) | `pytest tests/test_scout.py::test_deduplication -x` | Wave 0 |
| All | Heartbeat file written on successful run | unit | `pytest tests/test_scout.py::test_heartbeat_written -x` | Wave 0 |
| All | Heartbeat NOT written if pipeline crashes before completion | unit | `pytest tests/test_scout.py::test_heartbeat_not_written_on_crash -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_scout.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_scout.py` — covers all INGEST-01, INGEST-02, INTEL-01 test cases above
- [ ] `src/pipeline/__init__.py` — new module init file
- [ ] `src/pipeline/scout.py` — main implementation module (stub exists in trigger.py)
- [ ] `requirements.txt` update — add `arxiv>=2.4,<3`
- [ ] Signals schema migration — add `reasoning` TEXT property (idempotent)

---

## Sources

### Primary (HIGH confidence)
- [arxiv API User's Manual](https://info.arxiv.org/help/api/user-manual.html) — submittedDate format, category filter syntax, query operators
- [arxiv.py GitHub README](https://github.com/lukasschwab/arxiv.py) — Client + Search class API, SortCriterion, Result fields
- [Weaviate similarity search docs](https://docs.weaviate.io/weaviate/search/similarity) — near_text/near_vector collection query API
- Existing codebase: `src/runtime/claude_runner.py`, `src/db/schema.py`, `src/db/client.py`, `src/api/routes/trigger.py`, `tests/test_claude_runner.py`

### Secondary (MEDIUM confidence)
- [Weaviate Python client readthedocs v4.14.2](https://weaviate-python-client.readthedocs.io/en/v4.14.2/weaviate.collections.queries.near_text.html) — near_text parameters, MetadataQuery, Filter.by_property
- [WebSearch: arxiv.py submittedDate wildcard pattern](https://github.com/ContentMine/getpapers/issues/180) — `submittedDate:YYYYMMDD*` wildcard confirmed

### Tertiary (LOW confidence)
- None — all critical claims have primary or secondary verification

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in requirements.txt or locked by project
- Architecture: HIGH — patterns derived from existing codebase conventions + official docs
- Pitfalls: MEDIUM — arxiv_id normalization and Haiku JSON fallback from known arxiv.py behaviors; schema gap from direct code inspection

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (stable libraries; arxiv.py and Weaviate v4 API are stable)
