"""Unit tests for manual seed ingestion (ingest_manual_seed)."""

import uuid
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test 1: ingest_manual_seed writes Signal with status="manual", tier="BRIEF", score=0.0
# ---------------------------------------------------------------------------

def test_ingest_manual_seed_writes_signal_with_correct_defaults():
    """ingest_manual_seed writes a Signal with status=manual, tier=BRIEF, score=0.0."""
    mock_obj = MagicMock()
    mock_response = MagicMock()
    mock_response.objects = []  # No duplicate

    mock_collection = MagicMock()
    mock_collection.query.fetch_objects.return_value = mock_response
    inserted_uuid = str(uuid.uuid4())
    mock_collection.data.insert.return_value = inserted_uuid

    mock_client = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    with patch("src.pipeline.ingest.get_client", return_value=mock_client):
        from src.pipeline.ingest import ingest_manual_seed
        result = ingest_manual_seed({"title": "Test Paper", "url": "https://example.com"})

    mock_collection.data.insert.assert_called_once()
    inserted_data = mock_collection.data.insert.call_args[0][0]
    assert inserted_data["status"] == "manual"
    assert inserted_data["tier"] == "BRIEF"
    assert inserted_data["score"] == 0.0
    assert inserted_data["title"] == "Test Paper"
    assert inserted_data["source_url"] == "https://example.com"
    assert result is not None


# ---------------------------------------------------------------------------
# Test 2: notes stored in abstract field when no abstract provided
# ---------------------------------------------------------------------------

def test_ingest_manual_seed_stores_notes_as_abstract():
    """Notes are stored in abstract field when no abstract is provided."""
    mock_response = MagicMock()
    mock_response.objects = []

    mock_collection = MagicMock()
    mock_collection.query.fetch_objects.return_value = mock_response
    mock_collection.data.insert.return_value = str(uuid.uuid4())

    mock_client = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    with patch("src.pipeline.ingest.get_client", return_value=mock_client):
        from src.pipeline.ingest import ingest_manual_seed
        ingest_manual_seed({
            "title": "Interesting Finding",
            "url": "https://example.com/paper",
            "notes": "This is a key insight about agents",
        })

    inserted_data = mock_collection.data.insert.call_args[0][0]
    assert inserted_data["abstract"] == "This is a key insight about agents"


# ---------------------------------------------------------------------------
# Test 3: ingest_manual_seed skips duplicate source_url (idempotent)
# ---------------------------------------------------------------------------

def test_ingest_manual_seed_skips_duplicate_source_url():
    """ingest_manual_seed does NOT insert when source_url already exists."""
    existing_uuid = str(uuid.uuid4())
    mock_existing_obj = MagicMock()
    mock_existing_obj.uuid = existing_uuid

    mock_response = MagicMock()
    mock_response.objects = [mock_existing_obj]  # Duplicate found

    mock_collection = MagicMock()
    mock_collection.query.fetch_objects.return_value = mock_response

    mock_client = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    with patch("src.pipeline.ingest.get_client", return_value=mock_client):
        from src.pipeline.ingest import ingest_manual_seed
        result = ingest_manual_seed({"title": "Duplicate", "url": "https://example.com"})

    mock_collection.data.insert.assert_not_called()
    assert result == existing_uuid


# ---------------------------------------------------------------------------
# Test 4: explicit abstract takes precedence over notes
# ---------------------------------------------------------------------------

def test_ingest_manual_seed_abstract_takes_precedence_over_notes():
    """When both abstract and notes are provided, abstract is used."""
    mock_response = MagicMock()
    mock_response.objects = []

    mock_collection = MagicMock()
    mock_collection.query.fetch_objects.return_value = mock_response
    mock_collection.data.insert.return_value = str(uuid.uuid4())

    mock_client = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    with patch("src.pipeline.ingest.get_client", return_value=mock_client):
        from src.pipeline.ingest import ingest_manual_seed
        ingest_manual_seed({
            "title": "Paper",
            "url": "https://example.com",
            "abstract": "The real abstract",
            "notes": "Some notes",
        })

    inserted_data = mock_collection.data.insert.call_args[0][0]
    assert inserted_data["abstract"] == "The real abstract"


# ---------------------------------------------------------------------------
# Test 5: client is closed after insert (try/finally lifecycle)
# ---------------------------------------------------------------------------

def test_ingest_manual_seed_closes_client():
    """Weaviate client is closed in finally block."""
    mock_response = MagicMock()
    mock_response.objects = []

    mock_collection = MagicMock()
    mock_collection.query.fetch_objects.return_value = mock_response
    mock_collection.data.insert.return_value = str(uuid.uuid4())

    mock_client = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    with patch("src.pipeline.ingest.get_client", return_value=mock_client):
        from src.pipeline.ingest import ingest_manual_seed
        ingest_manual_seed({"title": "Paper", "url": "https://example.com"})

    mock_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test 6: client is closed even on exception
# ---------------------------------------------------------------------------

def test_ingest_manual_seed_closes_client_on_error():
    """Weaviate client is closed in finally block even when an error occurs."""
    mock_collection = MagicMock()
    mock_collection.query.fetch_objects.side_effect = RuntimeError("Weaviate down")

    mock_client = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    with patch("src.pipeline.ingest.get_client", return_value=mock_client):
        from src.pipeline.ingest import ingest_manual_seed
        with pytest.raises(RuntimeError):
            ingest_manual_seed({"title": "Paper", "url": "https://example.com"})

    mock_client.close.assert_called_once()
