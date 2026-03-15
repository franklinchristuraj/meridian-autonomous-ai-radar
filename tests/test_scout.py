"""Unit tests for Scout pipeline helper functions."""

import json
import os
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.pipeline.scout import (
    assign_tier,
    arxiv_id_exists,
    build_arxiv_query,
    fetch_arxiv_papers,
    fetch_pattern_keywords,
    get_top_patterns,
    keyword_density,
    keyword_filter,
    normalize_arxiv_id,
    run_scout_pipeline,
    score_paper,
    write_heartbeat,
    write_signal,
)


# ---------------------------------------------------------------------------
# build_arxiv_query
# ---------------------------------------------------------------------------

def test_build_arxiv_query():
    """Query string contains all 6 categories and submittedDate wildcard."""
    q = build_arxiv_query(date(2024, 1, 15))
    assert "cs.AI" in q
    assert "cs.CL" in q
    assert "cs.CV" in q
    assert "cs.LG" in q
    assert "cs.MA" in q
    assert "cs.SD" in q
    assert "submittedDate:20240115*" in q


# ---------------------------------------------------------------------------
# fetch_arxiv_papers
# ---------------------------------------------------------------------------

def test_fetch_arxiv_papers():
    """fetch_arxiv_papers returns a list of Result-like objects for a given date."""
    mock_result = MagicMock()
    mock_result.entry_id = "http://arxiv.org/abs/2401.12345v1"
    mock_result.title = "Test Paper"
    mock_result.summary = "Abstract text"
    mock_result.published = date(2024, 1, 15)
    mock_result.primary_category = "cs.AI"

    mock_client_instance = MagicMock()
    mock_client_instance.results.return_value = iter([mock_result])

    with patch("arxiv.Client", return_value=mock_client_instance):
        with patch("arxiv.Search") as mock_search:
            results = fetch_arxiv_papers(date(2024, 1, 15))

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].entry_id == "http://arxiv.org/abs/2401.12345v1"


# ---------------------------------------------------------------------------
# normalize_arxiv_id
# ---------------------------------------------------------------------------

def test_normalize_arxiv_id_with_version():
    """Full URL with version suffix -> bare ID."""
    assert normalize_arxiv_id("http://arxiv.org/abs/2401.12345v1") == "2401.12345"


def test_normalize_arxiv_id_no_version():
    """Full URL without version suffix -> bare ID."""
    assert normalize_arxiv_id("http://arxiv.org/abs/2401.12345") == "2401.12345"


# ---------------------------------------------------------------------------
# fetch_pattern_keywords
# ---------------------------------------------------------------------------

def test_fetch_pattern_keywords():
    """Returns deduplicated lowercase keyword list from Weaviate Patterns."""
    mock_obj1 = MagicMock()
    mock_obj1.properties = {"keywords": ["Agent", "Orchestration"]}
    mock_obj2 = MagicMock()
    mock_obj2.properties = {"keywords": ["agent", "RAG"]}  # duplicate 'agent' in different case

    mock_response = MagicMock()
    mock_response.objects = [mock_obj1, mock_obj2]

    mock_collection = MagicMock()
    mock_collection.query.fetch_objects.return_value = mock_response

    mock_client = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    keywords = fetch_pattern_keywords(mock_client)

    assert isinstance(keywords, list)
    # All lowercase
    assert all(kw == kw.lower() for kw in keywords)
    # Deduplicated: "agent" appears twice across both objects but should be once
    assert keywords.count("agent") == 1
    assert "orchestration" in keywords
    assert "rag" in keywords


# ---------------------------------------------------------------------------
# keyword_density
# ---------------------------------------------------------------------------

def test_keyword_density():
    """Count of keywords found in text."""
    count = keyword_density("agent orchestration framework", ["agent", "orchestration"])
    assert count == 2


def test_keyword_density_case_insensitive():
    """keyword_density is case-insensitive."""
    count = keyword_density("Agent Orchestration Framework", ["agent", "orchestration"])
    assert count == 2


def test_keyword_density_no_match():
    """Returns 0 when no keywords found."""
    count = keyword_density("unrelated text here", ["agent", "orchestration"])
    assert count == 0


# ---------------------------------------------------------------------------
# keyword_filter
# ---------------------------------------------------------------------------

def _make_mock_paper(title, summary, entry_id="http://arxiv.org/abs/0000.00000v1"):
    p = MagicMock()
    p.title = title
    p.summary = summary
    p.entry_id = entry_id
    return p


def test_keyword_filter_cap():
    """Returns at most cap papers, ranked by keyword density."""
    keywords = ["agent", "rag", "llm", "embedding", "vector", "retrieval",
                "transformer", "attention", "fine-tuning", "inference"]
    # 100 papers: half with density 2, half with density 0
    papers = []
    for i in range(50):
        papers.append(_make_mock_paper(
            f"agent rag paper {i}", f"llm embedding abstract {i}",
            entry_id=f"http://arxiv.org/abs/2401.{i:05d}v1"
        ))
    for i in range(50, 100):
        papers.append(_make_mock_paper(
            f"unrelated paper {i}", f"unrelated abstract {i}",
            entry_id=f"http://arxiv.org/abs/2401.{i:05d}v1"
        ))

    result = keyword_filter(papers, keywords, cap=50)
    assert len(result) <= 50
    # All returned papers have keyword hits
    for p in result:
        assert keyword_density(p.title + " " + p.summary, keywords) > 0


def test_keyword_filter_excludes_zero_hits():
    """Papers with no keyword matches are excluded even under cap."""
    keywords = ["agent"]
    papers = [
        _make_mock_paper("agent paper", "some abstract"),
        _make_mock_paper("unrelated paper", "unrelated abstract"),
    ]
    result = keyword_filter(papers, keywords, cap=50)
    assert len(result) == 1
    assert result[0].title == "agent paper"


# ---------------------------------------------------------------------------
# get_top_patterns
# ---------------------------------------------------------------------------

def test_get_top_patterns():
    """Returns top N dicts with name, description, contrarian_take, keywords, uuid, distance."""
    mock_obj = MagicMock()
    mock_obj.properties = {
        "name": "Agentic Systems",
        "description": "Multi-agent coordination",
        "contrarian_take": "Agents may not be the answer",
        "keywords": ["agent", "multi-agent"],
    }
    mock_obj.uuid = "test-uuid-1234"
    mock_obj.metadata = MagicMock()
    mock_obj.metadata.distance = 0.15

    mock_response = MagicMock()
    mock_response.objects = [mock_obj]

    mock_collection = MagicMock()
    mock_collection.query.near_text.return_value = mock_response

    mock_client = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    results = get_top_patterns(mock_client, "Test Title", "Test Abstract", top_n=5)

    assert len(results) == 1
    assert results[0]["name"] == "Agentic Systems"
    assert results[0]["uuid"] == "test-uuid-1234"
    assert results[0]["distance"] == 0.15
    assert "keywords" in results[0]
    assert "contrarian_take" in results[0]

    # Verify near_text was called with correct args
    mock_collection.query.near_text.assert_called_once()
    call_kwargs = mock_collection.query.near_text.call_args
    assert call_kwargs.kwargs.get("limit") == 5 or call_kwargs.args[1] == 5


# ---------------------------------------------------------------------------
# score_paper
# ---------------------------------------------------------------------------

VALID_SCORE_JSON = json.dumps({
    "score": 7.5,
    "matched_pattern_names": ["Agentic Systems"],
    "reasoning": "This paper directly advances multi-agent coordination with novel benchmarks."
})

PATTERNS_LIST = [
    {
        "name": "Agentic Systems",
        "description": "Multi-agent coordination",
        "contrarian_take": "Agents may not be the answer",
        "keywords": ["agent"],
        "uuid": "abc-123",
        "distance": 0.1,
    }
]


def test_score_paper():
    """Parses valid JSON response from invoke_claude."""
    mock_raw = {"result": VALID_SCORE_JSON, "model": "claude-haiku-4-5", "usage": {}, "cost_usd": 0.001}
    with patch("src.pipeline.scout.invoke_claude", return_value=mock_raw):
        result = score_paper("Test Title", "Test Abstract", PATTERNS_LIST)

    assert result["score"] == 7.5
    assert result["matched_pattern_names"] == ["Agentic Systems"]
    assert "reasoning" in result


def test_score_paper_bad_json():
    """Regex fallback extracts JSON from prose-wrapped response."""
    prose_wrapped = f"Here is my analysis:\n{VALID_SCORE_JSON}\nThank you."
    mock_raw = {"result": prose_wrapped, "model": "claude-haiku-4-5", "usage": {}, "cost_usd": 0.001}
    with patch("src.pipeline.scout.invoke_claude", return_value=mock_raw):
        result = score_paper("Test Title", "Test Abstract", PATTERNS_LIST)

    assert result["score"] == 7.5
    assert "reasoning" in result


def test_score_paper_unparseable():
    """Raises ValueError when response cannot be parsed."""
    mock_raw = {"result": "This is completely garbage and has no JSON at all!", "model": "claude-haiku-4-5", "usage": {}, "cost_usd": 0.001}
    with patch("src.pipeline.scout.invoke_claude", return_value=mock_raw):
        with pytest.raises(ValueError):
            score_paper("Test Title", "Test Abstract", PATTERNS_LIST)


# ---------------------------------------------------------------------------
# assign_tier
# ---------------------------------------------------------------------------

def test_assign_tier():
    """Tier boundaries: >=7.0 BRIEF, >=5.0 VAULT, <5.0 ARCHIVE."""
    assert assign_tier(7.0) == "BRIEF"
    assert assign_tier(7.5) == "BRIEF"
    assert assign_tier(10.0) == "BRIEF"
    assert assign_tier(6.9) == "VAULT"
    assert assign_tier(5.0) == "VAULT"
    assert assign_tier(4.9) == "ARCHIVE"
    assert assign_tier(1.0) == "ARCHIVE"


# ---------------------------------------------------------------------------
# arxiv_id_exists
# ---------------------------------------------------------------------------

def test_arxiv_id_exists_true():
    """Returns True when Weaviate filter returns 1 object."""
    mock_obj = MagicMock()
    mock_response = MagicMock()
    mock_response.objects = [mock_obj]

    mock_collection = MagicMock()
    mock_collection.query.fetch_objects.return_value = mock_response

    mock_client = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    assert arxiv_id_exists(mock_client, "2401.12345") is True


def test_arxiv_id_exists_false():
    """Returns False when Weaviate filter returns 0 objects."""
    mock_response = MagicMock()
    mock_response.objects = []

    mock_collection = MagicMock()
    mock_collection.query.fetch_objects.return_value = mock_response

    mock_client = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    assert arxiv_id_exists(mock_client, "9999.99999") is False


# ---------------------------------------------------------------------------
# write_signal
# ---------------------------------------------------------------------------

def test_write_signal_new():
    """Calls insert when arxiv_id does not yet exist."""
    mock_response = MagicMock()
    mock_response.objects = []

    mock_collection = MagicMock()
    mock_collection.query.fetch_objects.return_value = mock_response

    mock_client = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    data = {"arxiv_id": "2401.99999", "title": "New Paper", "score": 8.0}
    write_signal(mock_client, data)

    mock_collection.data.insert.assert_called_once_with(data)


def test_write_signal_duplicate():
    """Does NOT call insert when arxiv_id already exists."""
    mock_obj = MagicMock()
    mock_response = MagicMock()
    mock_response.objects = [mock_obj]

    mock_collection = MagicMock()
    mock_collection.query.fetch_objects.return_value = mock_response

    mock_client = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    data = {"arxiv_id": "2401.12345", "title": "Existing Paper", "score": 7.0}
    write_signal(mock_client, data)

    mock_collection.data.insert.assert_not_called()


# ---------------------------------------------------------------------------
# write_heartbeat
# ---------------------------------------------------------------------------

def test_write_heartbeat(tmp_path, monkeypatch):
    """Writes valid JSON with expected keys to heartbeat/scout.json."""
    import src.pipeline.scout as scout_module
    monkeypatch.setattr(scout_module, "HEARTBEAT_PATH", tmp_path / "scout.json")

    write_heartbeat(42, 10)

    assert (tmp_path / "scout.json").exists()
    data = json.loads((tmp_path / "scout.json").read_text())
    assert data["papers_fetched"] == 42
    assert data["papers_scored"] == 10
    assert data["status"] == "ok"
    assert "last_run" in data


def test_heartbeat_creates_directory(tmp_path, monkeypatch):
    """heartbeat/ dir is created if it does not exist."""
    import src.pipeline.scout as scout_module
    nested = tmp_path / "nested" / "heartbeat" / "scout.json"
    monkeypatch.setattr(scout_module, "HEARTBEAT_PATH", nested)

    write_heartbeat(5, 3)

    assert nested.exists()


# ---------------------------------------------------------------------------
# run_scout_pipeline
# ---------------------------------------------------------------------------

def _make_paper(entry_id, title="Title", summary="Abstract"):
    p = MagicMock()
    p.entry_id = entry_id
    p.title = title
    p.summary = summary
    p.published = MagicMock()
    p.published.isoformat.return_value = "2024-01-15T00:00:00"
    return p


MOCK_PATTERNS = [
    {"name": "P1", "description": "desc1", "contrarian_take": "ct1",
     "keywords": ["kw"], "uuid": "uuid-1", "distance": 0.1}
]

MOCK_SCORE_RESULT = {
    "score": 8.0,
    "matched_pattern_names": ["P1"],
    "reasoning": "Novel contribution.",
}


@patch("src.pipeline.scout.write_heartbeat")
@patch("src.pipeline.scout.write_signal")
@patch("src.pipeline.scout.assign_tier", return_value="BRIEF")
@patch("src.pipeline.scout.score_paper", return_value=MOCK_SCORE_RESULT)
@patch("src.pipeline.scout.get_top_patterns", return_value=MOCK_PATTERNS)
@patch("src.pipeline.scout.arxiv_id_exists", return_value=False)
@patch("src.pipeline.scout.keyword_filter")
@patch("src.pipeline.scout.fetch_pattern_keywords", return_value=["agent"])
@patch("src.pipeline.scout.fetch_arxiv_papers")
@patch("src.pipeline.scout.get_client")
def test_run_scout_pipeline_happy_path(
    mock_get_client, mock_fetch, mock_keywords, mock_filter,
    mock_exists, mock_top, mock_score, mock_tier, mock_write, mock_heartbeat
):
    """Happy path: fetch -> keywords -> filter -> score loop -> write -> heartbeat. Client closed."""
    papers = [
        _make_paper("http://arxiv.org/abs/2401.00001v1", "Paper 1"),
        _make_paper("http://arxiv.org/abs/2401.00002v1", "Paper 2"),
        _make_paper("http://arxiv.org/abs/2401.00003v1", "Paper 3"),
    ]
    mock_fetch.return_value = papers
    mock_filter.return_value = papers

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    run_scout_pipeline()

    assert mock_write.call_count == 3
    mock_heartbeat.assert_called_once_with(3, 3)
    mock_client.close.assert_called_once()


@patch("src.pipeline.scout.write_heartbeat")
@patch("src.pipeline.scout.write_signal")
@patch("src.pipeline.scout.assign_tier", return_value="VAULT")
@patch("src.pipeline.scout.score_paper", return_value=MOCK_SCORE_RESULT)
@patch("src.pipeline.scout.get_top_patterns", return_value=MOCK_PATTERNS)
@patch("src.pipeline.scout.arxiv_id_exists")
@patch("src.pipeline.scout.keyword_filter")
@patch("src.pipeline.scout.fetch_pattern_keywords", return_value=["agent"])
@patch("src.pipeline.scout.fetch_arxiv_papers")
@patch("src.pipeline.scout.get_client")
def test_run_scout_pipeline_skips_duplicates(
    mock_get_client, mock_fetch, mock_keywords, mock_filter,
    mock_exists, mock_top, mock_score, mock_tier, mock_write, mock_heartbeat
):
    """Paper 2 is a duplicate — score_paper not called for it."""
    papers = [
        _make_paper("http://arxiv.org/abs/2401.00001v1", "Paper 1"),
        _make_paper("http://arxiv.org/abs/2401.00002v1", "Paper 2"),
        _make_paper("http://arxiv.org/abs/2401.00003v1", "Paper 3"),
    ]
    mock_fetch.return_value = papers
    mock_filter.return_value = papers
    # Paper 2 (index 1) is a duplicate
    mock_exists.side_effect = [False, True, False]

    mock_get_client.return_value = MagicMock()

    run_scout_pipeline()

    assert mock_score.call_count == 2
    mock_heartbeat.assert_called_once_with(3, 2)


@patch("src.pipeline.scout.write_heartbeat")
@patch("src.pipeline.scout.write_signal")
@patch("src.pipeline.scout.assign_tier", return_value="VAULT")
@patch("src.pipeline.scout.score_paper")
@patch("src.pipeline.scout.get_top_patterns", return_value=MOCK_PATTERNS)
@patch("src.pipeline.scout.arxiv_id_exists", return_value=False)
@patch("src.pipeline.scout.keyword_filter")
@patch("src.pipeline.scout.fetch_pattern_keywords", return_value=["agent"])
@patch("src.pipeline.scout.fetch_arxiv_papers")
@patch("src.pipeline.scout.get_client")
def test_run_scout_pipeline_score_failure_continues(
    mock_get_client, mock_fetch, mock_keywords, mock_filter,
    mock_exists, mock_top, mock_score, mock_tier, mock_write, mock_heartbeat
):
    """Score failure for paper 2 is logged and skipped; pipeline continues; heartbeat written."""
    papers = [
        _make_paper("http://arxiv.org/abs/2401.00001v1", "Paper 1"),
        _make_paper("http://arxiv.org/abs/2401.00002v1", "Paper 2"),
        _make_paper("http://arxiv.org/abs/2401.00003v1", "Paper 3"),
    ]
    mock_fetch.return_value = papers
    mock_filter.return_value = papers
    mock_score.side_effect = [MOCK_SCORE_RESULT, Exception("Haiku failed"), MOCK_SCORE_RESULT]

    mock_get_client.return_value = MagicMock()

    run_scout_pipeline()

    assert mock_write.call_count == 2
    mock_heartbeat.assert_called_once_with(3, 2)


@patch("src.pipeline.scout.fetch_arxiv_papers", side_effect=RuntimeError("network error"))
@patch("src.pipeline.scout.get_client")
def test_run_scout_pipeline_client_closed_on_error(mock_get_client, mock_fetch):
    """Client is closed in finally block even when fetch raises."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    with pytest.raises(RuntimeError):
        run_scout_pipeline()

    mock_client.close.assert_called_once()


@patch("src.pipeline.scout.write_heartbeat")
@patch("src.pipeline.scout.fetch_arxiv_papers", side_effect=RuntimeError("network error"))
@patch("src.pipeline.scout.get_client")
def test_run_scout_pipeline_no_heartbeat_on_crash(mock_get_client, mock_fetch, mock_heartbeat):
    """Heartbeat is NOT written when pipeline crashes before completion."""
    mock_get_client.return_value = MagicMock()

    with pytest.raises(RuntimeError):
        run_scout_pipeline()

    mock_heartbeat.assert_not_called()
