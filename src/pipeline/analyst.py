"""Analyst pipeline module.

Clusters today's scored signals into 5-8 thematic groups, annotates trends,
and writes cluster_id back to Signal objects in Weaviate.

Workflow:
  signals = fetch_todays_signals(client)
  history = fetch_recent_signals(client, days=7)
  clusters = cluster_signals(signals, history, client)
  write_cluster_ids(client, clusters)
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from weaviate import WeaviateClient
from weaviate.classes.query import Filter

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from src.runtime.claude_runner import invoke_claude

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer("meridian.pipeline")

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

ANALYST_PROMPT_TEMPLATE = """\
You are an intelligence analyst clustering AI research signals into thematic groups.

## Today's Signals
{signals_block}

## 7-Day History (for trend context)
{history_block}

## Task
Group the signals into 5-8 thematic clusters following these rules:
1. ANCHOR FIRST: Signals sharing the same matched_pattern_ids MUST be placed in the same cluster.
2. SEMANTIC GROUPING: Use semantic similarity to group remaining signals.
3. TARGET: Aim for 5-8 clusters total. Do not create more than 8 or fewer than 5 unless signal count forces it.
4. TREND ANNOTATION: If a cluster's topic appeared 2 or more times in the 7-day history, set trend_annotation to a brief sentence noting the trend. Otherwise set it to null.
5. SINGLETONS: Signals that do not fit any cluster go in the singletons list as their uuid string.

Respond ONLY with valid JSON matching this exact schema — no prose, no markdown fences:
{{
  "clusters": [
    {{
      "cluster_id": "<string, e.g. cluster_001>",
      "theme_summary": "<1 sentence describing the cluster topic>",
      "signal_ids": ["<uuid>", ...],
      "matched_pattern_ids": ["<pattern_uuid>", ...],
      "trend_annotation": "<string or null>"
    }}
  ],
  "singletons": ["<uuid>", ...]
}}
"""


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def fetch_todays_signals(client: WeaviateClient) -> list[dict]:
    """Query Signals for BRIEF+VAULT signals published yesterday or today.

    Returns list of dicts with keys:
      uuid, title, abstract, score, tier, matched_pattern_ids, reasoning
    Limit 100.
    """
    signals_col = client.collections.get("Signals")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    response = signals_col.query.fetch_objects(
        filters=(
            Filter.by_property("tier").contains_any(["BRIEF", "VAULT"])
            & Filter.by_property("published_date").greater_or_equal(yesterday.isoformat())
        ),
        limit=100,
    )

    return [
        {
            "uuid": str(obj.uuid),
            "title": obj.properties.get("title", ""),
            "abstract": obj.properties.get("abstract", ""),
            "score": obj.properties.get("score", 0.0),
            "tier": obj.properties.get("tier", ""),
            "matched_pattern_ids": obj.properties.get("matched_pattern_ids") or [],
            "reasoning": obj.properties.get("reasoning", ""),
        }
        for obj in response.objects
    ]


def fetch_recent_signals(client: WeaviateClient, days: int = 7) -> list[dict]:
    """Query Signals for BRIEF+VAULT signals from the last `days` days.

    Returns lighter payload: list of dicts with keys: title, matched_pattern_ids
    """
    signals_col = client.collections.get("Signals")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    response = signals_col.query.fetch_objects(
        filters=(
            Filter.by_property("tier").contains_any(["BRIEF", "VAULT"])
            & Filter.by_property("published_date").greater_or_equal(cutoff.isoformat())
        ),
        limit=500,
    )

    return [
        {
            "title": obj.properties.get("title", ""),
            "matched_pattern_ids": obj.properties.get("matched_pattern_ids") or [],
        }
        for obj in response.objects
    ]


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def _build_signals_block(signals: list[dict]) -> str:
    lines = []
    for s in signals:
        pids = ", ".join(s.get("matched_pattern_ids") or []) or "none"
        lines.append(
            f"- uuid={s['uuid']} | tier={s.get('tier','')} | score={s.get('score','')} "
            f"| patterns=[{pids}] | title={s.get('title','')}"
        )
    return "\n".join(lines) if lines else "(none)"


def _build_history_block(history: list[dict]) -> str:
    lines = []
    for h in history:
        pids = ", ".join(h.get("matched_pattern_ids") or []) or "none"
        lines.append(f"- patterns=[{pids}] | title={h.get('title','')}")
    return "\n".join(lines) if lines else "(no history)"


def _parse_cluster_response(result_text: str) -> dict:
    """Parse cluster JSON from Claude response. Tries direct parse, then regex fallback."""
    # Direct parse
    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        pass

    # Regex fallback: extract outermost {...} block (same pattern as score_paper in scout.py)
    match = re.search(r'\{.*\}', result_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.error(f"cluster_signals: unparseable Sonnet response: {result_text!r}")
    raise ValueError(f"Cannot parse Sonnet clustering response as JSON: {result_text!r}")


def cluster_signals(signals: list[dict], history: list[dict], client: WeaviateClient) -> dict:
    """Cluster today's signals into 5-8 thematic groups using Sonnet.

    Args:
        signals: Today's BRIEF+VAULT signals (from fetch_todays_signals).
        history: Last 7 days of signals for trend context (from fetch_recent_signals).
        client: Weaviate client (passed for interface consistency; not used directly here).

    Returns:
        dict with keys:
          clusters: list of cluster dicts (cluster_id, theme_summary, signal_ids,
                    matched_pattern_ids, trend_annotation)
          singletons: list of uuid strings
    """
    with _tracer.start_as_current_span("meridian.stage.analyst") as span:
        try:
            span.set_attribute("analyst.signals_count", len(signals))
            span.set_attribute("analyst.history_count", len(history))

            signals_block = _build_signals_block(signals)
            history_block = _build_history_block(history)

            prompt = ANALYST_PROMPT_TEMPLATE.format(
                signals_block=signals_block,
                history_block=history_block,
            )

            raw = invoke_claude(prompt, model="claude-sonnet-4-5", timeout=300)
            result_text = raw["result"]

            result = _parse_cluster_response(result_text)

            span.set_attribute("analyst.clusters_found", len(result.get("clusters", [])))
            span.set_attribute("analyst.singletons_count", len(result.get("singletons", [])))
            span.set_status(StatusCode.OK)
            return result
        except Exception as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            raise


# ---------------------------------------------------------------------------
# Write-back
# ---------------------------------------------------------------------------

def write_cluster_ids(client: WeaviateClient, clusters: dict) -> None:
    """Write cluster_id back to each Signal object in Weaviate.

    For signals in a cluster: sets cluster_id = cluster["cluster_id"].
    For singletons: sets cluster_id = "singleton".
    """
    signals_col = client.collections.get("Signals")

    for cluster in clusters.get("clusters", []):
        cid = cluster["cluster_id"]
        for uuid in cluster.get("signal_ids", []):
            signals_col.data.update(uuid=uuid, properties={"cluster_id": cid})

    for uuid in clusters.get("singletons", []):
        signals_col.data.update(uuid=uuid, properties={"cluster_id": "singleton"})
