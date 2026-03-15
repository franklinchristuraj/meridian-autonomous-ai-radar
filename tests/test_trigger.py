"""Tests for the pipeline trigger endpoint."""

import pytest
from unittest.mock import patch
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("X_API_KEY", "test-secret")


@pytest.fixture
def client():
    from src.api.main import app
    return TestClient(app)


def test_trigger_accepts_seed_payload(client):
    """POST /pipeline/trigger with valid key + JSON body {title, url} returns 202."""
    with patch("src.api.routes.trigger.ingest_manual_seed") as mock_ingest:
        mock_ingest.return_value = "some-uuid"
        response = client.post(
            "/pipeline/trigger",
            headers={"X-API-Key": "test-secret"},
            json={"title": "Test Paper", "url": "https://example.com"},
        )
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_trigger_returns_202(client):
    """POST /pipeline/trigger with valid X-API-Key returns 202 and accepted body."""
    with patch("src.api.routes.trigger.ingest_manual_seed"):
        response = client.post(
            "/pipeline/trigger",
            headers={"X-API-Key": "test-secret"},
            json={"title": "Test Paper", "url": "https://example.com"},
        )
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_trigger_missing_title_returns_422(client):
    """POST /pipeline/trigger with valid key but missing title returns 422."""
    response = client.post(
        "/pipeline/trigger",
        headers={"X-API-Key": "test-secret"},
        json={"url": "https://example.com"},
    )
    assert response.status_code == 422


def test_trigger_rejects_bad_key(client):
    """POST /pipeline/trigger with wrong X-API-Key returns 403."""
    response = client.post(
        "/pipeline/trigger",
        headers={"X-API-Key": "wrong-key"},
        json={"title": "Test Paper"},
    )
    assert response.status_code == 403


def test_trigger_rejects_missing_key(client):
    """POST /pipeline/trigger without X-API-Key header returns 403."""
    response = client.post(
        "/pipeline/trigger",
        json={"title": "Test Paper"},
    )
    assert response.status_code == 403
