"""Tests for the pipeline trigger endpoint."""

import os
import pytest
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("X_API_KEY", "test-secret")


@pytest.fixture
def client():
    from src.api.main import app
    return TestClient(app)


def test_trigger_returns_202(client):
    """POST /pipeline/trigger with valid X-API-Key returns 202 and accepted body."""
    response = client.post(
        "/pipeline/trigger",
        headers={"X-API-Key": "test-secret"},
    )
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}


def test_trigger_rejects_bad_key(client):
    """POST /pipeline/trigger with wrong X-API-Key returns 403."""
    response = client.post(
        "/pipeline/trigger",
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 403


def test_trigger_rejects_missing_key(client):
    """POST /pipeline/trigger without X-API-Key header returns 403."""
    response = client.post("/pipeline/trigger")
    assert response.status_code == 403
