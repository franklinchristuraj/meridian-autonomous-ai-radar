"""Unit tests for briefing API routes."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TODAY = "2026-03-15"
YESTERDAY = "2026-03-14"

SAMPLE_BRIEFING_OBJ = {
    "summary": "AI research activity remains strong across agentic coordination and LLMOps. Multi-agent frameworks dominate BRIEF-tier signals. Continued volume expected.",
    "generated_at": f"{TODAY}T06:05:00+00:00",
    "date": f"{TODAY}T00:00:00Z",
    "item_count": 2,
    "items_json": json.dumps([
        {
            "cluster_id": "cluster_001",
            "what_happening": "Multi-agent coordination frameworks are rapidly maturing.",
            "time_horizon": "0-3 months",
            "recommended_action": "Consider updating pattern AGENTIC-01.",
            "tier": "BRIEF",
        },
        {
            "cluster_id": "cluster_002",
            "what_happening": "LoRA fine-tuning is becoming standard.",
            "time_horizon": "3-6 months",
            "recommended_action": "Read the full papers.",
            "tier": "VAULT",
        },
    ]),
}

YESTERDAY_BRIEFING_OBJ = {
    **SAMPLE_BRIEFING_OBJ,
    "date": f"{YESTERDAY}T00:00:00Z",
    "generated_at": f"{YESTERDAY}T06:05:00+00:00",
}

FRESH_HEARTBEAT = {
    "last_run": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    "signals_processed": 20,
    "clusters_generated": 4,
    "status": "ok",
}

STALE_HEARTBEAT = {
    "last_run": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(),
    "signals_processed": 15,
    "clusters_generated": 3,
    "status": "ok",
}


def _make_weaviate_obj(props: dict) -> MagicMock:
    obj = MagicMock()
    obj.properties = props
    obj.uuid = "mock-uuid-001"
    return obj


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("X_API_KEY", "test-secret")


@pytest.fixture
def client():
    from src.api.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helper: mock get_briefing_for_date result
# ---------------------------------------------------------------------------

def _patch_get_briefing(result_obj):
    """Returns a context manager patching get_briefing_for_date to return result_obj."""
    return patch(
        "src.api.routes.briefing.get_briefing_for_date",
        return_value=result_obj,
    )


def _patch_staleness(stale: bool, last_run=None, hours=None):
    return patch(
        "src.api.routes.briefing.get_briefing_staleness",
        return_value={"stale": stale, "last_run": last_run, "hours_since_run": hours},
    )


# ---------------------------------------------------------------------------
# POST /briefing/generate
# ---------------------------------------------------------------------------

def test_generate_trigger_202(client):
    """POST /briefing/generate with valid key returns 202."""
    with patch("src.api.routes.briefing.run_analyst_briefing_pipeline"):
        response = client.post(
            "/briefing/generate",
            headers={"X-API-Key": "test-secret"},
        )
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_generate_trigger_403(client):
    """POST /briefing/generate without key returns 403."""
    response = client.post("/briefing/generate")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /briefing/today/narrative
# ---------------------------------------------------------------------------

def test_today_narrative(client):
    """GET /briefing/today/narrative returns summary text + staleness info."""
    with (
        _patch_get_briefing(SAMPLE_BRIEFING_OBJ),
        _patch_staleness(False, FRESH_HEARTBEAT["last_run"], 1.0),
    ):
        response = client.get("/briefing/today/narrative")

    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "generated_at" in data
    assert "stale" in data
    assert data["stale"] is False


def test_today_narrative_no_briefing(client):
    """GET /briefing/today/narrative returns 404 when no briefing exists for today."""
    with _patch_get_briefing(None):
        response = client.get("/briefing/today/narrative")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /briefing/today/data
# ---------------------------------------------------------------------------

def test_today_data(client):
    """GET /briefing/today/data returns structured JSON with clusters, items, staleness."""
    with (
        _patch_get_briefing(SAMPLE_BRIEFING_OBJ),
        _patch_staleness(False, FRESH_HEARTBEAT["last_run"], 1.0),
    ):
        response = client.get("/briefing/today/data")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "item_count" in data
    assert "date" in data
    assert "stale" in data
    assert isinstance(data["items"], list)


# ---------------------------------------------------------------------------
# GET /briefing/{date}/narrative and /data
# ---------------------------------------------------------------------------

def test_date_narrative(client):
    """GET /briefing/2026-03-14/narrative returns that date's briefing."""
    with (
        _patch_get_briefing(YESTERDAY_BRIEFING_OBJ),
        _patch_staleness(True, STALE_HEARTBEAT["last_run"], 30.0),
    ):
        response = client.get(f"/briefing/{YESTERDAY}/narrative")

    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "generated_at" in data


def test_date_data(client):
    """GET /briefing/2026-03-14/data returns structured JSON for that date."""
    with (
        _patch_get_briefing(YESTERDAY_BRIEFING_OBJ),
        _patch_staleness(True, STALE_HEARTBEAT["last_run"], 30.0),
    ):
        response = client.get(f"/briefing/{YESTERDAY}/data")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "item_count" in data
    assert "date" in data


# ---------------------------------------------------------------------------
# Staleness detection
# ---------------------------------------------------------------------------

def test_staleness_true(tmp_path, monkeypatch):
    """Staleness flag is true when heartbeat >25 hours old."""
    from src.api.routes.briefing import get_briefing_staleness

    heartbeat_file = tmp_path / "briefing.json"
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    heartbeat_file.write_text(json.dumps({"last_run": stale_time, "status": "ok"}))

    import src.api.routes.briefing as briefing_module
    monkeypatch.setattr(briefing_module, "BRIEFING_HEARTBEAT_PATH", heartbeat_file)

    result = get_briefing_staleness()
    assert result["stale"] is True
    assert result["last_run"] is not None
    assert result["hours_since_run"] > 25


def test_staleness_no_heartbeat(tmp_path, monkeypatch):
    """Staleness flag is true with last_run=null when no heartbeat file exists."""
    from src.api.routes.briefing import get_briefing_staleness

    import src.api.routes.briefing as briefing_module
    monkeypatch.setattr(briefing_module, "BRIEFING_HEARTBEAT_PATH", tmp_path / "nonexistent.json")

    result = get_briefing_staleness()
    assert result["stale"] is True
    assert result["last_run"] is None
    assert result["hours_since_run"] is None


def test_staleness_fresh(tmp_path, monkeypatch):
    """Staleness flag is false when heartbeat <25 hours old."""
    from src.api.routes.briefing import get_briefing_staleness

    heartbeat_file = tmp_path / "briefing.json"
    fresh_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    heartbeat_file.write_text(json.dumps({"last_run": fresh_time, "status": "ok"}))

    import src.api.routes.briefing as briefing_module
    monkeypatch.setattr(briefing_module, "BRIEFING_HEARTBEAT_PATH", heartbeat_file)

    result = get_briefing_staleness()
    assert result["stale"] is False
    assert result["hours_since_run"] < 25
