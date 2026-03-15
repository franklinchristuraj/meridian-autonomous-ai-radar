"""Scout pipeline helper functions.

Daily workflow: fetch ArXiv papers → keyword filter → score with Haiku → write Signals.
Each function is independently testable and importable.
"""

import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path

import arxiv
from weaviate import WeaviateClient
from weaviate.classes.query import Filter, MetadataQuery

from src.db.client import get_client
from src.runtime.claude_runner import invoke_claude

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORIES = ["cs.AI", "cs.CL", "cs.CV", "cs.LG", "cs.MA", "cs.SD"]

HEARTBEAT_PATH = Path("heartbeat/scout.json")

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


# ---------------------------------------------------------------------------
# ArXiv helpers
# ---------------------------------------------------------------------------

def build_arxiv_query(target_date: date) -> str:
    """Build an ArXiv query string for 6 categories on a specific date."""
    date_str = target_date.strftime("%Y%m%d")
    cat_filter = " OR ".join(f"cat:{c}" for c in CATEGORIES)
    return f"({cat_filter}) AND submittedDate:{date_str}*"


def fetch_arxiv_papers(target_date: date | None = None) -> list:
    """Fetch ArXiv papers for target_date (defaults to yesterday).

    Returns a list of arxiv.Result objects.
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    client = arxiv.Client(num_retries=3, page_size=100)
    search = arxiv.Search(
        query=build_arxiv_query(target_date),
        max_results=500,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    return list(client.results(search))


def normalize_arxiv_id(entry_id: str) -> str:
    """Normalize entry_id URL to bare arxiv ID (no URL prefix, no version suffix).

    Example: "http://arxiv.org/abs/2401.12345v1" -> "2401.12345"
    """
    return entry_id.split("/abs/")[-1].split("v")[0]


# ---------------------------------------------------------------------------
# Keyword filter helpers
# ---------------------------------------------------------------------------

def fetch_pattern_keywords(client: WeaviateClient) -> list[str]:
    """Fetch all keywords from Weaviate Patterns collection, deduplicated and lowercased."""
    patterns = client.collections.get("Patterns")
    response = patterns.query.fetch_objects(return_properties=["keywords"])
    keywords: list[str] = []
    for obj in response.objects:
        keywords.extend(obj.properties.get("keywords", []))
    return list(set(kw.lower() for kw in keywords))


def keyword_density(text: str, keywords: list[str]) -> int:
    """Count how many keywords appear in text (case-insensitive)."""
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw in text_lower)


def keyword_filter(papers: list, keywords: list[str], cap: int = 50) -> list:
    """Score papers by keyword density, exclude 0-hit papers, sort desc, return top cap."""
    scored = [
        (p, keyword_density(p.title + " " + p.summary, keywords))
        for p in papers
    ]
    scored = [(p, s) for p, s in scored if s > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:cap]]


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------

def get_top_patterns(
    client: WeaviateClient,
    title: str,
    abstract: str,
    top_n: int = 5,
) -> list[dict]:
    """Return top_n patterns most semantically similar to the paper's title+abstract.

    Uses Weaviate near_text (text2vec_transformers vectorizer handles embedding).
    """
    patterns = client.collections.get("Patterns")
    text_to_match = f"{title}\n\n{abstract}"
    response = patterns.query.near_text(
        query=text_to_match,
        limit=top_n,
        return_metadata=MetadataQuery(distance=True),
    )
    return [
        {
            "name": obj.properties.get("name"),
            "description": obj.properties.get("description"),
            "contrarian_take": obj.properties.get("contrarian_take"),
            "keywords": obj.properties.get("keywords", []),
            "uuid": str(obj.uuid),
            "distance": obj.metadata.distance,
        }
        for obj in response.objects
    ]


# ---------------------------------------------------------------------------
# Haiku scoring
# ---------------------------------------------------------------------------

def score_paper(title: str, abstract: str, patterns: list[dict]) -> dict:
    """Score a paper against its top patterns using Claude Haiku.

    Returns dict with keys: score, matched_pattern_names, reasoning.
    Raises ValueError if the response cannot be parsed as JSON.
    """
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
    result_text = raw["result"]

    # Try direct parse first
    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        pass

    # Regex fallback: extract {...} block from prose-wrapped response
    match = re.search(r'\{.*\}', result_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.error(f"score_paper: unparseable Haiku response: {result_text!r}")
    raise ValueError(f"Cannot parse Haiku response as JSON: {result_text!r}")


# ---------------------------------------------------------------------------
# Tier assignment
# ---------------------------------------------------------------------------

def assign_tier(score: float) -> str:
    """Map numeric score to tier string.

    >= 7.0 -> BRIEF
    >= 5.0 -> VAULT
    < 5.0  -> ARCHIVE
    """
    if score >= 7.0:
        return "BRIEF"
    if score >= 5.0:
        return "VAULT"
    return "ARCHIVE"


# ---------------------------------------------------------------------------
# Signal deduplication and write
# ---------------------------------------------------------------------------

def arxiv_id_exists(client: WeaviateClient, arxiv_id: str) -> bool:
    """Return True if a Signal with this arxiv_id already exists in Weaviate."""
    signals = client.collections.get("Signals")
    response = signals.query.fetch_objects(
        filters=Filter.by_property("arxiv_id").equal(arxiv_id),
        limit=1,
    )
    return len(response.objects) > 0


def write_signal(client: WeaviateClient, data: dict) -> None:
    """Write a Signal to Weaviate, skipping if arxiv_id already exists (idempotent)."""
    if arxiv_id_exists(client, data["arxiv_id"]):
        logger.debug(f"write_signal: skipping duplicate arxiv_id={data['arxiv_id']}")
        return
    signals = client.collections.get("Signals")
    signals.data.insert(data)


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

def write_heartbeat(paper_count: int, scored_count: int) -> None:
    """Write a JSON heartbeat file on successful pipeline completion."""
    import json as _json
    from datetime import datetime, timezone
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_PATH.write_text(_json.dumps({
        "last_run": datetime.now(timezone.utc).isoformat(),
        "papers_fetched": paper_count,
        "papers_scored": scored_count,
        "status": "ok",
    }))


# ---------------------------------------------------------------------------
# Pipeline orchestrator (wired in Plan 02)
# ---------------------------------------------------------------------------

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
            arxiv_id = normalize_arxiv_id(paper.entry_id)
            if arxiv_id_exists(client, arxiv_id):
                continue
            try:
                patterns = get_top_patterns(client, paper.title, paper.summary)
                result = score_paper(paper.title, paper.summary, patterns)
                score = float(result["score"])
                tier = assign_tier(score)
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

        from src.pipeline.briefing import run_analyst_briefing_pipeline
        run_analyst_briefing_pipeline()
    finally:
        client.close()
