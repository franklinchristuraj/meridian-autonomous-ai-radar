"""Unit tests for src/pipeline/analyst.py — Analyst agent (clustering + trend annotations)."""

import json
import re
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call

import pytest

from src.db.schema import _migrate_signals_cluster_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(
    uuid: str,
    title: str = "Test Signal",
    tier: str = "BRIEF",
    score: float = 7.5,
    matched_pattern_ids: list[str] | None = None,
    published_date: str | None = None,
) -> dict:
    return {
        "uuid": uuid,
        "title": title,
        "abstract": f"Abstract for {title}",
        "score": score,
        "tier": tier,
        "matched_pattern_ids": matched_pattern_ids or [],
        "reasoning": "Test reasoning",
        "published_date": published_date or datetime.now(timezone.utc).isoformat(),
    }


def _make_mock_weaviate_object(uuid: str, properties: dict) -> MagicMock:
    obj = MagicMock()
    obj.uuid = uuid
    obj.properties = properties
    return obj


def _make_cluster_response(clusters: list[dict] | None = None, singletons: list[str] | None = None) -> dict:
    return {
        "clusters": clusters or [
            {
                "cluster_id": "cluster_001",
                "theme_summary": "Agentic LLM frameworks",
                "signal_ids": ["uuid-1", "uuid-2"],
                "matched_pattern_ids": ["pat-1"],
                "trend_annotation": None,
            }
        ],
        "singletons": singletons or [],
    }


# ---------------------------------------------------------------------------
# Schema migration tests
# ---------------------------------------------------------------------------

class TestMigrateSignalsClusterId:
    def test_idempotent_first_call(self):
        """Calling _migrate_signals_cluster_id once should add the property."""
        client = MagicMock()
        signals_col = MagicMock()
        client.collections.exists.return_value = True
        client.collections.get.return_value = signals_col

        _migrate_signals_cluster_id(client)

        signals_col.config.add_property.assert_called_once()

    def test_idempotent_second_call(self):
        """Calling _migrate_signals_cluster_id twice does not raise (property-exists exception swallowed)."""
        client = MagicMock()
        signals_col = MagicMock()
        client.collections.exists.return_value = True
        client.collections.get.return_value = signals_col
        # Second call: add_property raises (simulating "already exists")
        signals_col.config.add_property.side_effect = [None, Exception("property already exists")]

        # Should not raise
        _migrate_signals_cluster_id(client)
        _migrate_signals_cluster_id(client)

    def test_no_op_when_signals_missing(self):
        """Migration is a no-op when Signals collection does not exist."""
        client = MagicMock()
        client.collections.exists.return_value = False

        _migrate_signals_cluster_id(client)

        client.collections.get.assert_not_called()


# ---------------------------------------------------------------------------
# fetch_todays_signals tests
# ---------------------------------------------------------------------------

class TestFetchTodaysSignals:
    def test_returns_brief_and_vault_signals(self):
        """fetch_todays_signals returns BRIEF+VAULT signals with expected properties."""
        from src.pipeline.analyst import fetch_todays_signals

        client = MagicMock()
        signals_col = MagicMock()
        client.collections.get.return_value = signals_col

        obj1 = _make_mock_weaviate_object("uuid-1", {
            "title": "Paper A",
            "abstract": "Abstract A",
            "score": 8.0,
            "tier": "BRIEF",
            "matched_pattern_ids": ["pat-1"],
            "reasoning": "Good paper",
        })
        obj2 = _make_mock_weaviate_object("uuid-2", {
            "title": "Paper B",
            "abstract": "Abstract B",
            "score": 6.0,
            "tier": "VAULT",
            "matched_pattern_ids": ["pat-2"],
            "reasoning": "Decent paper",
        })
        signals_col.query.fetch_objects.return_value.objects = [obj1, obj2]

        results = fetch_todays_signals(client)

        assert len(results) == 2
        assert results[0]["uuid"] == "uuid-1"
        assert results[0]["title"] == "Paper A"
        assert results[0]["tier"] == "BRIEF"
        assert "matched_pattern_ids" in results[0]

    def test_returns_expected_property_keys(self):
        """Each returned signal dict has uuid, title, abstract, score, tier, matched_pattern_ids, reasoning."""
        from src.pipeline.analyst import fetch_todays_signals

        client = MagicMock()
        signals_col = MagicMock()
        client.collections.get.return_value = signals_col

        obj = _make_mock_weaviate_object("uuid-1", {
            "title": "Paper A",
            "abstract": "Abstract A",
            "score": 8.0,
            "tier": "BRIEF",
            "matched_pattern_ids": ["pat-1"],
            "reasoning": "Solid",
        })
        signals_col.query.fetch_objects.return_value.objects = [obj]

        results = fetch_todays_signals(client)

        expected_keys = {"uuid", "title", "abstract", "score", "tier", "matched_pattern_ids", "reasoning"}
        assert expected_keys.issubset(set(results[0].keys()))


# ---------------------------------------------------------------------------
# fetch_recent_signals tests
# ---------------------------------------------------------------------------

class TestFetchRecentSignals:
    def test_returns_signals_from_last_7_days(self):
        """fetch_recent_signals returns signals covering last 7 days."""
        from src.pipeline.analyst import fetch_recent_signals

        client = MagicMock()
        signals_col = MagicMock()
        client.collections.get.return_value = signals_col

        obj = _make_mock_weaviate_object("uuid-10", {
            "title": "Old Paper",
            "matched_pattern_ids": ["pat-3"],
        })
        signals_col.query.fetch_objects.return_value.objects = [obj]

        results = fetch_recent_signals(client, days=7)

        assert len(results) == 1
        assert results[0]["title"] == "Old Paper"
        assert "matched_pattern_ids" in results[0]

    def test_returns_lighter_payload(self):
        """fetch_recent_signals returns only title + matched_pattern_ids."""
        from src.pipeline.analyst import fetch_recent_signals

        client = MagicMock()
        signals_col = MagicMock()
        client.collections.get.return_value = signals_col

        obj = _make_mock_weaviate_object("uuid-11", {
            "title": "Trend Paper",
            "matched_pattern_ids": ["pat-4"],
        })
        signals_col.query.fetch_objects.return_value.objects = [obj]

        results = fetch_recent_signals(client)

        assert set(results[0].keys()) == {"title", "matched_pattern_ids"}


# ---------------------------------------------------------------------------
# cluster_signals tests
# ---------------------------------------------------------------------------

SAMPLE_CLUSTER_JSON = json.dumps({
    "clusters": [
        {"cluster_id": "cluster_001", "theme_summary": "Agentic AI", "signal_ids": ["uuid-1", "uuid-2", "uuid-3"], "matched_pattern_ids": ["pat-1"], "trend_annotation": None},
        {"cluster_id": "cluster_002", "theme_summary": "RAG Systems", "signal_ids": ["uuid-4", "uuid-5"], "matched_pattern_ids": ["pat-2"], "trend_annotation": None},
        {"cluster_id": "cluster_003", "theme_summary": "LLMOps", "signal_ids": ["uuid-6", "uuid-7"], "matched_pattern_ids": ["pat-3"], "trend_annotation": None},
        {"cluster_id": "cluster_004", "theme_summary": "Multimodal", "signal_ids": ["uuid-8", "uuid-9"], "matched_pattern_ids": ["pat-4"], "trend_annotation": None},
        {"cluster_id": "cluster_005", "theme_summary": "Evaluation", "signal_ids": ["uuid-10", "uuid-11"], "matched_pattern_ids": ["pat-5"], "trend_annotation": None},
    ],
    "singletons": ["uuid-12", "uuid-13"],
})


class TestClusterSignals:
    def _make_signals(self, n: int) -> list[dict]:
        return [_make_signal(f"uuid-{i+1}", title=f"Paper {i+1}", matched_pattern_ids=[f"pat-{(i % 5) + 1}"]) for i in range(n)]

    def test_pattern_anchor_grouping(self):
        """Signals sharing matched_pattern_ids are grouped into same cluster."""
        from src.pipeline.analyst import cluster_signals

        shared_pat = "pat-shared"
        signals = [
            _make_signal("uuid-A", matched_pattern_ids=[shared_pat]),
            _make_signal("uuid-B", matched_pattern_ids=[shared_pat]),
            _make_signal("uuid-C", matched_pattern_ids=["pat-other"]),
        ]
        history = []

        cluster_json = json.dumps({
            "clusters": [
                {"cluster_id": "cluster_001", "theme_summary": "Group A", "signal_ids": ["uuid-A", "uuid-B"], "matched_pattern_ids": [shared_pat], "trend_annotation": None},
                {"cluster_id": "cluster_002", "theme_summary": "Group C", "signal_ids": ["uuid-C"], "matched_pattern_ids": ["pat-other"], "trend_annotation": None},
            ],
            "singletons": [],
        })

        mock_client = MagicMock()
        with patch("src.pipeline.analyst.invoke_claude") as mock_claude:
            mock_claude.return_value = {"result": cluster_json}
            result = cluster_signals(signals, history, mock_client)

        cluster_001 = next(c for c in result["clusters"] if c["cluster_id"] == "cluster_001")
        assert "uuid-A" in cluster_001["signal_ids"]
        assert "uuid-B" in cluster_001["signal_ids"]

    def test_singletons_returned_separately(self):
        """Signals that don't cluster are returned in singletons list."""
        from src.pipeline.analyst import cluster_signals

        signals = self._make_signals(10)
        history = []

        cluster_json = json.dumps({
            "clusters": [
                {"cluster_id": "cluster_001", "theme_summary": "Topic A", "signal_ids": ["uuid-1", "uuid-2"], "matched_pattern_ids": ["pat-1"], "trend_annotation": None},
            ],
            "singletons": ["uuid-9", "uuid-10"],
        })

        mock_client = MagicMock()
        with patch("src.pipeline.analyst.invoke_claude") as mock_claude:
            mock_claude.return_value = {"result": cluster_json}
            result = cluster_signals(signals, history, mock_client)

        assert "uuid-9" in result["singletons"]
        assert "uuid-10" in result["singletons"]

    def test_target_count_5_to_8_clusters(self):
        """Output has 5-8 clusters for a typical day (mock 20+ signals)."""
        from src.pipeline.analyst import cluster_signals

        signals = self._make_signals(22)
        history = []

        mock_client = MagicMock()
        with patch("src.pipeline.analyst.invoke_claude") as mock_claude:
            mock_claude.return_value = {"result": SAMPLE_CLUSTER_JSON}
            result = cluster_signals(signals, history, mock_client)

        cluster_count = len(result["clusters"])
        assert 5 <= cluster_count <= 8, f"Expected 5-8 clusters, got {cluster_count}"

    def test_trend_annotations_populated(self):
        """cluster output includes trend_annotation when history shows repeated topic."""
        from src.pipeline.analyst import cluster_signals

        signals = [_make_signal("uuid-1", matched_pattern_ids=["pat-trend"])]
        history = [{"title": "Old Trend Paper", "matched_pattern_ids": ["pat-trend"]}]

        annotated_json = json.dumps({
            "clusters": [
                {
                    "cluster_id": "cluster_001",
                    "theme_summary": "Trending Topic",
                    "signal_ids": ["uuid-1"],
                    "matched_pattern_ids": ["pat-trend"],
                    "trend_annotation": "This topic has appeared 3 times in the last 7 days.",
                }
            ],
            "singletons": [],
        })

        mock_client = MagicMock()
        with patch("src.pipeline.analyst.invoke_claude") as mock_claude:
            mock_claude.return_value = {"result": annotated_json}
            result = cluster_signals(signals, history, mock_client)

        cluster = result["clusters"][0]
        assert cluster["trend_annotation"] is not None
        assert len(cluster["trend_annotation"]) > 0

    def test_invalid_json_regex_fallback(self):
        """Handles malformed Sonnet response wrapped in prose using regex fallback."""
        from src.pipeline.analyst import cluster_signals

        signals = [_make_signal("uuid-1")]
        history = []

        cluster_json = json.dumps({
            "clusters": [
                {"cluster_id": "cluster_001", "theme_summary": "Agentic AI", "signal_ids": ["uuid-1"], "matched_pattern_ids": ["pat-1"], "trend_annotation": None}
            ],
            "singletons": [],
        })
        prose_wrapped = f"Here is the clustering result:\n\n{cluster_json}\n\nLet me know if you need anything else."

        mock_client = MagicMock()
        with patch("src.pipeline.analyst.invoke_claude") as mock_claude:
            mock_claude.return_value = {"result": prose_wrapped}
            result = cluster_signals(signals, history, mock_client)

        assert "clusters" in result
        assert len(result["clusters"]) == 1

    def test_required_cluster_keys_present(self):
        """Each cluster dict contains all required keys."""
        from src.pipeline.analyst import cluster_signals

        signals = self._make_signals(10)
        history = []

        mock_client = MagicMock()
        with patch("src.pipeline.analyst.invoke_claude") as mock_claude:
            mock_claude.return_value = {"result": SAMPLE_CLUSTER_JSON}
            result = cluster_signals(signals, history, mock_client)

        required_keys = {"cluster_id", "theme_summary", "signal_ids", "matched_pattern_ids", "trend_annotation"}
        for cluster in result["clusters"]:
            assert required_keys.issubset(set(cluster.keys())), f"Missing keys in cluster: {cluster}"

    def test_invoke_claude_called_with_correct_args(self):
        """cluster_signals calls invoke_claude with model=claude-sonnet-4-5 and timeout=300."""
        from src.pipeline.analyst import cluster_signals

        signals = [_make_signal("uuid-1")]
        history = []

        mock_client = MagicMock()
        with patch("src.pipeline.analyst.invoke_claude") as mock_claude:
            mock_claude.return_value = {"result": json.dumps({"clusters": [], "singletons": []})}
            cluster_signals(signals, history, mock_client)

        mock_claude.assert_called_once()
        _, kwargs = mock_claude.call_args
        assert kwargs.get("model") == "claude-sonnet-4-5"
        assert kwargs.get("timeout") == 300


# ---------------------------------------------------------------------------
# write_cluster_ids tests
# ---------------------------------------------------------------------------

class TestWriteClusterIds:
    def test_cluster_id_written_to_signals(self):
        """cluster_id property is updated on each Signal object in Weaviate."""
        from src.pipeline.analyst import write_cluster_ids

        client = MagicMock()
        signals_col = MagicMock()
        client.collections.get.return_value = signals_col

        clusters_data = {
            "clusters": [
                {"cluster_id": "cluster_001", "theme_summary": "Agentic AI", "signal_ids": ["uuid-1", "uuid-2"], "matched_pattern_ids": ["pat-1"], "trend_annotation": None},
            ],
            "singletons": ["uuid-3"],
        }

        write_cluster_ids(client, clusters_data)

        # Check cluster signals were updated
        calls = signals_col.data.update.call_args_list
        uuids_updated = [c.kwargs["uuid"] for c in calls]
        assert "uuid-1" in uuids_updated
        assert "uuid-2" in uuids_updated

    def test_singletons_get_singleton_cluster_id(self):
        """Singletons get cluster_id='singleton'."""
        from src.pipeline.analyst import write_cluster_ids

        client = MagicMock()
        signals_col = MagicMock()
        client.collections.get.return_value = signals_col

        clusters_data = {
            "clusters": [],
            "singletons": ["uuid-singleton-1", "uuid-singleton-2"],
        }

        write_cluster_ids(client, clusters_data)

        calls = signals_col.data.update.call_args_list
        singleton_calls = [c for c in calls if c.kwargs.get("properties", {}).get("cluster_id") == "singleton"]
        singleton_uuids = [c.kwargs["uuid"] for c in singleton_calls]
        assert "uuid-singleton-1" in singleton_uuids
        assert "uuid-singleton-2" in singleton_uuids

    def test_correct_cluster_id_assigned(self):
        """Each signal gets the cluster_id of its cluster (not a different one)."""
        from src.pipeline.analyst import write_cluster_ids

        client = MagicMock()
        signals_col = MagicMock()
        client.collections.get.return_value = signals_col

        clusters_data = {
            "clusters": [
                {"cluster_id": "cluster_AAA", "theme_summary": "Topic A", "signal_ids": ["uuid-A"], "matched_pattern_ids": [], "trend_annotation": None},
                {"cluster_id": "cluster_BBB", "theme_summary": "Topic B", "signal_ids": ["uuid-B"], "matched_pattern_ids": [], "trend_annotation": None},
            ],
            "singletons": [],
        }

        write_cluster_ids(client, clusters_data)

        calls = {c.kwargs["uuid"]: c.kwargs["properties"]["cluster_id"] for c in signals_col.data.update.call_args_list}
        assert calls["uuid-A"] == "cluster_AAA"
        assert calls["uuid-B"] == "cluster_BBB"
