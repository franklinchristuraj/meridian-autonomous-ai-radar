"""Briefing API routes — trigger and read endpoints."""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Security

from src.api.auth import verify_api_key
from src.pipeline.briefing import (
    BRIEFING_HEARTBEAT_PATH,
    run_analyst_briefing_pipeline,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/briefing", tags=["briefing"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_briefing_staleness() -> dict:
    """Read heartbeat/briefing.json and compute staleness.

    Returns dict with:
      stale: bool (True if >25 hours since last run, or no heartbeat)
      last_run: ISO string or None
      hours_since_run: float or None
    """
    if not BRIEFING_HEARTBEAT_PATH.exists():
        return {"stale": True, "last_run": None, "hours_since_run": None}

    try:
        hb = json.loads(BRIEFING_HEARTBEAT_PATH.read_text())
        last_run_str = hb.get("last_run")
        if not last_run_str:
            return {"stale": True, "last_run": None, "hours_since_run": None}

        last_run_dt = datetime.fromisoformat(last_run_str)
        now = datetime.now(timezone.utc)
        if last_run_dt.tzinfo is None:
            last_run_dt = last_run_dt.replace(tzinfo=timezone.utc)
        hours_since = (now - last_run_dt).total_seconds() / 3600
        return {
            "stale": hours_since > 25,
            "last_run": last_run_str,
            "hours_since_run": round(hours_since, 2),
        }
    except Exception as e:
        logger.warning(f"get_briefing_staleness: error reading heartbeat: {e}")
        return {"stale": True, "last_run": None, "hours_since_run": None}


def get_briefing_for_date(client, target_date: str) -> dict | None:  # type: ignore[type-arg]
    """Query Briefings collection for a specific date.

    Returns the briefing object as a dict, or None if not found.
    """
    from weaviate.classes.query import Filter

    briefings_col = client.collections.get("Briefings")
    date_start = f"{target_date}T00:00:00Z"

    # Compute next day
    d = date.fromisoformat(target_date)
    next_day = (d + timedelta(days=1)).isoformat()
    date_end = f"{next_day}T00:00:00Z"

    response = briefings_col.query.fetch_objects(
        filters=(
            Filter.by_property("date").greater_or_equal(date_start)
            & Filter.by_property("date").less_than(date_end)
        ),
        limit=1,
    )

    if not response.objects:
        return None

    obj = response.objects[0]
    return {
        "summary": obj.properties.get("summary", ""),
        "generated_at": obj.properties.get("generated_at", ""),
        "date": obj.properties.get("date", ""),
        "item_count": obj.properties.get("item_count", 0),
        "items_json": obj.properties.get("items_json", "[]"),
    }


def _get_client_and_briefing(target_date: str) -> dict:
    """Get briefing for a date, returning the raw dict or raising 404."""
    from src.db.client import get_client

    client = get_client()
    try:
        briefing = get_briefing_for_date(client, target_date)
    finally:
        client.close()

    if briefing is None:
        raise HTTPException(status_code=404, detail=f"No briefing found for {target_date}")
    return briefing


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/generate", status_code=202)
async def generate_briefing(
    background_tasks: BackgroundTasks,
    _key: str = Security(verify_api_key),
) -> dict:
    """Manually trigger the Analyst + Briefing pipeline."""
    background_tasks.add_task(run_analyst_briefing_pipeline)
    return {"status": "accepted"}


@router.get("/today/narrative")
async def get_today_narrative() -> dict:
    """Return today's briefing narrative text with staleness info."""
    today = date.today().isoformat()
    briefing = _get_client_and_briefing(today)
    staleness = get_briefing_staleness()
    return {
        "summary": briefing["summary"],
        "generated_at": briefing["generated_at"],
        **staleness,
    }


@router.get("/today/data")
async def get_today_data() -> dict:
    """Return today's structured briefing data (items, clusters) with staleness info."""
    today = date.today().isoformat()
    briefing = _get_client_and_briefing(today)
    staleness = get_briefing_staleness()
    return {
        "items": json.loads(briefing["items_json"]),
        "item_count": briefing["item_count"],
        "date": briefing["date"],
        **staleness,
    }


@router.get("/{target_date}/narrative")
async def get_date_narrative(target_date: str) -> dict:
    """Return narrative briefing for a specific date (YYYY-MM-DD)."""
    briefing = _get_client_and_briefing(target_date)
    staleness = get_briefing_staleness()
    return {
        "summary": briefing["summary"],
        "generated_at": briefing["generated_at"],
        **staleness,
    }


@router.get("/{target_date}/data")
async def get_date_data(target_date: str) -> dict:
    """Return structured briefing data for a specific date (YYYY-MM-DD)."""
    briefing = _get_client_and_briefing(target_date)
    staleness = get_briefing_staleness()
    return {
        "items": json.loads(briefing["items_json"]),
        "item_count": briefing["item_count"],
        "date": briefing["date"],
        **staleness,
    }
