"""Briefing pipeline module.

Generates structured morning narratives from Analyst clusters.

Workflow:
  run_analyst_briefing_pipeline()
    -> fetch_todays_signals + fetch_recent_signals
    -> cluster_signals + write_cluster_ids
    -> generate_briefing_narrative
    -> write_briefing + write_briefing_heartbeat
"""

import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path

from src.db.client import get_client
from src.pipeline.analyst import (
    cluster_signals,
    fetch_recent_signals,
    fetch_todays_signals,
    write_cluster_ids,
)
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from src.runtime.claude_runner import invoke_claude

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BRIEFING_HEARTBEAT_PATH = Path("heartbeat/briefing.json")

BRIEFING_PROMPT_TEMPLATE = """\
You are a strategic intelligence advisor producing a morning briefing from clustered AI research signals.

## Today's Signal Clusters
{clusters_block}

## Individual Signal Details
{signals_block}

## Task
Produce a morning briefing for a forward-intelligence practitioner. Your tone is that of an opinionated strategic advisor — direct, forward-looking, and willing to make recommendations.

Rules:
1. executive_summary: Exactly 3 sentences covering: (1) what's hot today, (2) any surprises or anomalies, (3) overall signal volume/trend.
2. items: Up to 10 items maximum. BRIEF-tier clusters MUST appear first (strategic priority), then VAULT-tier fill.
3. For BRIEF items: recommended_action MUST be strategic — e.g., "Consider updating pattern X with new evidence" or "Monitor for convergence with pattern Y".
4. For VAULT items: recommended_action MUST be read/investigate — e.g., "Read the full paper for implementation details" or "Investigate methodology for applicability".
5. Include trend_annotation context in what_happening where available.

Respond ONLY with valid JSON matching this exact schema — no prose, no markdown fences:
{{
  "executive_summary": "<3 sentences>",
  "items": [
    {{
      "cluster_id": "<string>",
      "what_happening": "<1-2 sentences describing the cluster>",
      "time_horizon": "<e.g. 0-3 months, 3-6 months, 6-12 months>",
      "recommended_action": "<action string>",
      "tier": "<BRIEF or VAULT>"
    }}
  ]
}}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_clusters_block(clusters: dict) -> str:
    lines = []
    for c in clusters.get("clusters", []):
        trend = c.get("trend_annotation") or "No trend annotation."
        lines.append(
            f"- cluster_id={c['cluster_id']} | theme={c['theme_summary']} "
            f"| signals={len(c.get('signal_ids', []))} | trend={trend}"
        )
    singletons = clusters.get("singletons", [])
    if singletons:
        lines.append(f"- singletons: {len(singletons)} signals did not fit any cluster")
    return "\n".join(lines) if lines else "(no clusters)"


def _build_signals_block(signals: list[dict]) -> str:
    lines = []
    for s in signals:
        lines.append(
            f"- uuid={s['uuid']} | tier={s.get('tier', '')} | score={s.get('score', '')} "
            f"| title={s.get('title', '')}"
        )
    return "\n".join(lines) if lines else "(no signals)"


def _parse_narrative_response(result_text: str) -> dict:
    """Parse narrative JSON from Claude response. Tries direct parse, then regex fallback."""
    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{.*\}', result_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.error(f"generate_briefing_narrative: unparseable Sonnet response: {result_text!r}")
    raise ValueError(f"Cannot parse Sonnet briefing response as JSON: {result_text!r}")


def _sort_and_cap_items(items: list[dict], max_items: int = 10) -> list[dict]:
    """Sort items BRIEF-first then VAULT, cap at max_items."""
    brief_items = [i for i in items if i.get("tier") == "BRIEF"]
    vault_items = [i for i in items if i.get("tier") == "VAULT"]
    other_items = [i for i in items if i.get("tier") not in ("BRIEF", "VAULT")]
    ordered = brief_items + vault_items + other_items
    return ordered[:max_items]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def generate_briefing_narrative(clusters: dict, signals: list[dict]) -> dict:
    """Generate a structured morning briefing narrative from clusters and signals.

    Calls Sonnet via invoke_claude with timeout=300. Parses response with
    json.loads + regex fallback. Validates required keys. Caps items at 10
    with BRIEF-tier first.

    Returns dict with executive_summary and items list.
    """
    clusters_block = _build_clusters_block(clusters)
    signals_block = _build_signals_block(signals)

    prompt = BRIEFING_PROMPT_TEMPLATE.format(
        clusters_block=clusters_block,
        signals_block=signals_block,
    )

    raw = invoke_claude(prompt, model="claude-sonnet-4-5", timeout=300)
    result_text = raw["result"]

    narrative = _parse_narrative_response(result_text)

    # Validate required top-level keys
    if "executive_summary" not in narrative:
        raise ValueError("Briefing narrative missing 'executive_summary'")
    if "items" not in narrative:
        raise ValueError("Briefing narrative missing 'items'")

    # Sort BRIEF first, cap at 10
    narrative["items"] = _sort_and_cap_items(narrative["items"])

    return narrative


def write_briefing(client, narrative: dict, clusters: dict) -> None:  # type: ignore[type-arg]
    """Write briefing to Weaviate Briefings collection with date deduplication.

    If a briefing already exists for today's date, deletes it before inserting.
    This makes the function idempotent — safe to re-run.
    """
    briefings_col = client.collections.get("Briefings")
    today_str = date.today().isoformat()
    today_start = f"{today_str}T00:00:00Z"
    tomorrow_str = (date.today().replace(day=date.today().day + 1) if date.today().day < 28
                    else _next_day_iso(today_str))
    tomorrow_start = f"{tomorrow_str}T00:00:00Z"

    from weaviate.classes.query import Filter
    existing = briefings_col.query.fetch_objects(
        filters=(
            Filter.by_property("date").greater_or_equal(today_start)
            & Filter.by_property("date").less_than(tomorrow_start)
        ),
        limit=1,
    )

    for obj in existing.objects:
        briefings_col.data.delete_by_id(str(obj.uuid))
        logger.info(f"write_briefing: deleted existing briefing {obj.uuid} for {today_str}")

    items = narrative.get("items", [])
    briefings_col.data.insert({
        "date": f"{today_str}T00:00:00Z",
        "summary": narrative.get("executive_summary", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "item_count": len(items),
        "items_json": json.dumps(items),
    })
    logger.info(f"write_briefing: wrote briefing for {today_str} with {len(items)} items")


def _next_day_iso(today_iso: str) -> str:
    """Return the next calendar day as ISO date string."""
    from datetime import timedelta
    d = date.fromisoformat(today_iso)
    return (d + timedelta(days=1)).isoformat()


def write_briefing_heartbeat(signal_count: int, cluster_count: int) -> None:
    """Write heartbeat/briefing.json on successful pipeline completion."""
    BRIEFING_HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BRIEFING_HEARTBEAT_PATH.write_text(json.dumps({
        "last_run": datetime.now(timezone.utc).isoformat(),
        "signals_processed": signal_count,
        "clusters_generated": cluster_count,
        "status": "ok",
    }))


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

def _run_translator_pipeline() -> None:
    """Delegate to run_translator_pipeline (lazy import avoids circular deps)."""
    from src.pipeline.translator import run_translator_pipeline
    run_translator_pipeline()


def run_analyst_briefing_pipeline() -> None:
    """Orchestrate Analyst + Briefing pipeline end-to-end.

    Steps:
      a. Concurrency guard: read heartbeat, return early if status=running
      b. Write running heartbeat
      c. Fetch today's signals + 7-day history
      d. Cluster signals, write cluster_ids back
      e. Generate narrative
      f. Write briefing to Weaviate
      g. Write ok heartbeat
    """
    # Concurrency guard
    if BRIEFING_HEARTBEAT_PATH.exists():
        try:
            hb = json.loads(BRIEFING_HEARTBEAT_PATH.read_text())
            if hb.get("status") == "running":
                logger.warning("run_analyst_briefing_pipeline: already running, skipping")
                return
        except Exception:
            pass  # Corrupt heartbeat — proceed anyway

    # Mark as running
    BRIEFING_HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BRIEFING_HEARTBEAT_PATH.write_text(json.dumps({
        "last_run": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }))

    client = get_client()
    try:
        with trace.get_tracer("meridian.pipeline").start_as_current_span("meridian.stage.briefing") as span:
            try:
                signals = fetch_todays_signals(client)
                span.set_attribute("briefing.signals_processed", len(signals))
                history = fetch_recent_signals(client, days=7)
                logger.info(f"Briefing pipeline: {len(signals)} signals, {len(history)} history items")

                clusters = cluster_signals(signals, history, client)
                span.set_attribute("briefing.clusters_generated", len(clusters.get("clusters", [])))
                write_cluster_ids(client, clusters)

                narrative = generate_briefing_narrative(clusters, signals)
                span.set_attribute("briefing.items_generated", len(narrative.get("items", [])))
                write_briefing(client, narrative, clusters)

                cluster_count = len(clusters.get("clusters", []))
                write_briefing_heartbeat(len(signals), cluster_count)
                span.set_status(StatusCode.OK)
                _run_translator_pipeline()
                logger.info(f"Briefing pipeline complete: {cluster_count} clusters, {len(narrative.get('items', []))} items")
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
                raise
    finally:
        client.close()
