"""Unit tests for vault API routes."""

from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("X_API_KEY", "test-secret")


@pytest.fixture
def client():
    from src.api.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_seed_file(
    seeds_dir: Path,
    filename: str,
    title: str,
    arxiv_url: str,
    signal_uuid: str = "uuid-abc123",
    created: str = "2026-03-15",
    confidence: float = 0.9,
    auto_deposit: bool = True,
) -> Path:
    """Write a minimal seed .md file with YAML frontmatter."""
    auto_deposit_line = "auto_deposit: true" if auto_deposit else "auto_deposit: false"
    content = f"""---
title: {title}
created: {created}
signal_uuid: {signal_uuid}
arxiv_url: {arxiv_url}
confidence: {confidence}
{auto_deposit_line}
---

# {title}

Seed content for testing.
"""
    path = seeds_dir / filename
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# POST /vault/deposit
# ---------------------------------------------------------------------------

def test_deposit_trigger_202(client):
    """POST /vault/deposit with valid X-API-Key returns 202 + {"status": "accepted"}."""
    with patch("src.pipeline.translator.run_translator_pipeline"):
        response = client.post(
            "/vault/deposit",
            headers={"X-API-Key": "test-secret"},
        )
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_deposit_trigger_403(client):
    """POST /vault/deposit without key returns 403."""
    response = client.post("/vault/deposit")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /vault/deposits
# ---------------------------------------------------------------------------

def test_list_deposits_empty(client, tmp_path):
    """GET /vault/deposits with empty seeds dir returns {"deposits": [], "count": 0}."""
    seeds_dir = tmp_path / "01_seeds"
    seeds_dir.mkdir()

    with patch("src.pipeline.translator.get_vault_seeds_path", return_value=seeds_dir):
        response = client.get("/vault/deposits")

    assert response.status_code == 200
    data = response.json()
    assert data["deposits"] == []
    assert data["count"] == 0


def test_list_deposits_with_seeds(client, tmp_path):
    """GET /vault/deposits with 2 auto-deposit seed files returns list of 2 dicts."""
    seeds_dir = tmp_path / "01_seeds"
    seeds_dir.mkdir()

    _write_seed_file(
        seeds_dir,
        "attention-is-all-you-need.md",
        "Attention Is All You Need",
        "https://arxiv.org/abs/1706.03762",
        signal_uuid="uuid-001",
        created="2026-03-15",
        auto_deposit=True,
    )
    _write_seed_file(
        seeds_dir,
        "chain-of-thought.md",
        "Chain of Thought Prompting",
        "https://arxiv.org/abs/2201.11903",
        signal_uuid="uuid-002",
        created="2026-03-15",
        auto_deposit=True,
    )

    with patch("src.pipeline.translator.get_vault_seeds_path", return_value=seeds_dir):
        response = client.get("/vault/deposits")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["deposits"]) == 2

    # Each deposit has required keys
    for deposit in data["deposits"]:
        assert "title" in deposit
        assert "created" in deposit
        assert "signal_uuid" in deposit
        assert "arxiv_url" in deposit


def test_list_deposits_ignores_non_auto(client, tmp_path):
    """GET /vault/deposits skips seed files without auto_deposit: true in frontmatter."""
    seeds_dir = tmp_path / "01_seeds"
    seeds_dir.mkdir()

    # One auto-deposited, one manual (no auto_deposit flag)
    _write_seed_file(
        seeds_dir,
        "auto-seed.md",
        "Auto Deposited Paper",
        "https://arxiv.org/abs/2000.00001",
        signal_uuid="uuid-auto",
        created="2026-03-15",
        auto_deposit=True,
    )
    _write_seed_file(
        seeds_dir,
        "manual-seed.md",
        "Manually Added Paper",
        "https://arxiv.org/abs/2000.00002",
        signal_uuid="uuid-manual",
        created="2026-03-15",
        auto_deposit=False,
    )

    with patch("src.pipeline.translator.get_vault_seeds_path", return_value=seeds_dir):
        response = client.get("/vault/deposits")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert len(data["deposits"]) == 1
    assert data["deposits"][0]["signal_uuid"] == "uuid-auto"
