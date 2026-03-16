"""Unit tests for briefing pipeline module."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, mock_open, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CLUSTERS = {
    "clusters": [
        {
            "cluster_id": "cluster_001",
            "theme_summary": "Multi-agent coordination frameworks",
            "signal_ids": ["uuid-1", "uuid-2"],
            "matched_pattern_ids": ["pat-001"],
            "trend_annotation": "Second week of strong multi-agent coverage.",
        },
        {
            "cluster_id": "cluster_002",
            "theme_summary": "LLM fine-tuning efficiency",
            "signal_ids": ["uuid-3"],
            "matched_pattern_ids": ["pat-002"],
            "trend_annotation": None,
        },
    ],
    "singletons": ["uuid-4"],
}

SAMPLE_SIGNALS = [
    {
        "uuid": "uuid-1",
        "title": "Agent coordination paper",
        "abstract": "We propose a novel multi-agent coordination framework.",
        "score": 8.5,
        "tier": "BRIEF",
        "matched_pattern_ids": ["pat-001"],
        "reasoning": "High relevance to agentic systems.",
    },
    {
        "uuid": "uuid-2",
        "title": "Multi-agent planning",
        "abstract": "Decentralized planning for agent networks.",
        "score": 7.2,
        "tier": "BRIEF",
        "matched_pattern_ids": ["pat-001"],
        "reasoning": "Directly advances coordination pattern.",
    },
    {
        "uuid": "uuid-3",
        "title": "LoRA fine-tuning at scale",
        "abstract": "Efficient fine-tuning using low-rank adaptation.",
        "score": 6.0,
        "tier": "VAULT",
        "matched_pattern_ids": ["pat-002"],
        "reasoning": "Relevant to LLMOps.",
    },
    {
        "uuid": "uuid-4",
        "title": "Random ML paper",
        "abstract": "A miscellaneous ML contribution.",
        "score": 5.5,
        "tier": "VAULT",
        "matched_pattern_ids": [],
        "reasoning": "Tangentially relevant.",
    },
]

SAMPLE_NARRATIVE = {
    "executive_summary": "AI research activity remains strong across agentic coordination and LLMOps. Multi-agent frameworks continue to dominate BRIEF-tier signals for the second week. Expect continued volume in coordination and fine-tuning spaces.",
    "items": [
        {
            "cluster_id": "cluster_001",
            "what_happening": "Multi-agent coordination frameworks are rapidly maturing.",
            "time_horizon": "0-3 months",
            "recommended_action": "Consider updating pattern AGENTIC-01 with new benchmarks.",
            "tier": "BRIEF",
        },
        {
            "cluster_id": "cluster_002",
            "what_happening": "LoRA-based fine-tuning is becoming the efficiency standard.",
            "time_horizon": "3-6 months",
            "recommended_action": "Read the full papers for implementation details.",
            "tier": "VAULT",
        },
    ],
}


def _make_claude_response(narrative: dict) -> dict:
    return {"result": json.dumps(narrative)}


# ---------------------------------------------------------------------------
# generate_briefing_narrative tests
# ---------------------------------------------------------------------------

class TestGenerateBriefingNarrative:
    def test_generate_briefing_narrative_structure(self):
        """Output contains executive_summary (3 sentences) and items list with required keys."""
        from src.pipeline.briefing import generate_briefing_narrative

        with patch("src.pipeline.briefing.invoke_claude") as mock_claude:
            mock_claude.return_value = _make_claude_response(SAMPLE_NARRATIVE)
            result = generate_briefing_narrative(SAMPLE_CLUSTERS, SAMPLE_SIGNALS)

        assert "executive_summary" in result
        assert "items" in result
        assert isinstance(result["items"], list)
        # Each item has required keys
        for item in result["items"]:
            assert "what_happening" in item
            assert "time_horizon" in item
            assert "recommended_action" in item
            assert "tier" in item

    def test_narrative_top_10_items(self):
        """Output has at most 10 items; BRIEF-tier clusters come before VAULT fill."""
        from src.pipeline.briefing import generate_briefing_narrative

        # Build narrative with exactly 12 items to test cap
        many_items = []
        for i in range(7):
            many_items.append({
                "cluster_id": f"cluster_{i:03d}",
                "what_happening": f"BRIEF event {i}",
                "time_horizon": "0-3 months",
                "recommended_action": "Consider updating pattern.",
                "tier": "BRIEF",
            })
        for i in range(5):
            many_items.append({
                "cluster_id": f"cluster_vault_{i:03d}",
                "what_happening": f"VAULT event {i}",
                "time_horizon": "6-12 months",
                "recommended_action": "Read the full paper.",
                "tier": "VAULT",
            })

        narrative_12 = {**SAMPLE_NARRATIVE, "items": many_items}

        with patch("src.pipeline.briefing.invoke_claude") as mock_claude:
            mock_claude.return_value = _make_claude_response(narrative_12)
            result = generate_briefing_narrative(SAMPLE_CLUSTERS, SAMPLE_SIGNALS)

        assert len(result["items"]) <= 10
        # BRIEF items should appear before VAULT items
        tiers = [item["tier"] for item in result["items"]]
        brief_indices = [i for i, t in enumerate(tiers) if t == "BRIEF"]
        vault_indices = [i for i, t in enumerate(tiers) if t == "VAULT"]
        if brief_indices and vault_indices:
            assert max(brief_indices) < min(vault_indices)

    def test_narrative_tiered_actions(self):
        """BRIEF items get strategic actions, VAULT items get read/investigate actions."""
        from src.pipeline.briefing import generate_briefing_narrative

        with patch("src.pipeline.briefing.invoke_claude") as mock_claude:
            mock_claude.return_value = _make_claude_response(SAMPLE_NARRATIVE)
            result = generate_briefing_narrative(SAMPLE_CLUSTERS, SAMPLE_SIGNALS)

        for item in result["items"]:
            action = item["recommended_action"].lower()
            if item["tier"] == "BRIEF":
                # Strategic actions: "consider", "update", "monitor", "evaluate"
                assert any(
                    word in action
                    for word in ["consider", "update", "monitor", "evaluate", "pattern"]
                ), f"BRIEF item missing strategic action: {item['recommended_action']}"
            elif item["tier"] == "VAULT":
                # Read/investigate actions
                assert any(
                    word in action
                    for word in ["read", "investigate", "review", "explore"]
                ), f"VAULT item missing read/investigate action: {item['recommended_action']}"

    def test_narrative_invalid_json(self):
        """Handles malformed Sonnet response with regex fallback."""
        from src.pipeline.briefing import generate_briefing_narrative

        # Prose-wrapped JSON (Claude sometimes adds explanation text)
        prose_response = (
            "Here is the briefing narrative as requested:\n"
            + json.dumps(SAMPLE_NARRATIVE)
            + "\nLet me know if you need adjustments."
        )

        with patch("src.pipeline.briefing.invoke_claude") as mock_claude:
            mock_claude.return_value = {"result": prose_response}
            result = generate_briefing_narrative(SAMPLE_CLUSTERS, SAMPLE_SIGNALS)

        assert "executive_summary" in result
        assert "items" in result


# ---------------------------------------------------------------------------
# write_briefing tests
# ---------------------------------------------------------------------------

class TestWriteBriefing:
    def _make_client_mock(self, existing_objects=None):
        """Build a minimal Weaviate client mock for Briefings collection."""
        mock_client = MagicMock()
        briefings_col = MagicMock()
        mock_client.collections.get.return_value = briefings_col

        # Simulate fetch_objects response
        fetch_response = MagicMock()
        if existing_objects:
            fetch_response.objects = existing_objects
        else:
            fetch_response.objects = []
        briefings_col.query.fetch_objects.return_value = fetch_response

        return mock_client, briefings_col

    def test_write_briefing(self):
        """Writes to Briefings collection with date, summary, generated_at, item_count, items_json."""
        from src.pipeline.briefing import write_briefing

        mock_client, briefings_col = self._make_client_mock()

        write_briefing(mock_client, SAMPLE_NARRATIVE, SAMPLE_CLUSTERS)

        briefings_col.data.insert.assert_called_once()
        call_kwargs = briefings_col.data.insert.call_args[0][0]

        assert "date" in call_kwargs
        assert "summary" in call_kwargs
        assert "generated_at" in call_kwargs
        assert "item_count" in call_kwargs
        assert "items_json" in call_kwargs
        assert call_kwargs["item_count"] == len(SAMPLE_NARRATIVE["items"])
        # items_json should be valid JSON
        parsed = json.loads(call_kwargs["items_json"])
        assert isinstance(parsed, list)

    def test_write_briefing_deduplication(self):
        """Re-running for same date deletes existing entry before reinserting."""
        from src.pipeline.briefing import write_briefing

        # Simulate existing briefing for today
        existing_obj = MagicMock()
        existing_obj.uuid = "existing-uuid-123"
        mock_client, briefings_col = self._make_client_mock(existing_objects=[existing_obj])

        write_briefing(mock_client, SAMPLE_NARRATIVE, SAMPLE_CLUSTERS)

        # Should have deleted the old entry
        briefings_col.data.delete_by_id.assert_called_once_with("existing-uuid-123")
        # Should insert new entry
        briefings_col.data.insert.assert_called_once()


# ---------------------------------------------------------------------------
# write_briefing_heartbeat tests
# ---------------------------------------------------------------------------

class TestWriteBriefingHeartbeat:
    def test_write_briefing_heartbeat(self):
        """Writes heartbeat/briefing.json with expected shape."""
        from src.pipeline.briefing import write_briefing_heartbeat

        mock_path = MagicMock()
        mock_path.parent = MagicMock()

        with patch("src.pipeline.briefing.BRIEFING_HEARTBEAT_PATH", mock_path):
            write_briefing_heartbeat(signal_count=10, cluster_count=3)

        mock_path.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_path.write_text.assert_called_once()

        written_text = mock_path.write_text.call_args[0][0]
        written_data = json.loads(written_text)

        assert "last_run" in written_data
        assert written_data["signals_processed"] == 10
        assert written_data["clusters_generated"] == 3
        assert written_data["status"] == "ok"


# ---------------------------------------------------------------------------
# run_analyst_briefing_pipeline tests
# ---------------------------------------------------------------------------

class TestRunAnalystBriefingPipeline:
    def _make_pipeline_mocks(self):
        """Return all mocks needed for a full pipeline run."""
        mock_client = MagicMock()
        return mock_client

    def test_run_analyst_briefing_pipeline(self):
        """Full orchestration calls fetch -> cluster -> write_cluster_ids -> generate -> write_briefing -> heartbeat."""
        from src.pipeline.briefing import run_analyst_briefing_pipeline

        mock_client = self._make_pipeline_mocks()

        with (
            patch("src.pipeline.briefing.BRIEFING_HEARTBEAT_PATH") as mock_hb_path,
            patch("src.pipeline.briefing.get_client", return_value=mock_client),
            patch("src.pipeline.briefing.fetch_todays_signals", return_value=SAMPLE_SIGNALS) as mock_fetch,
            patch("src.pipeline.briefing.fetch_recent_signals", return_value=[]) as mock_history,
            patch("src.pipeline.briefing.cluster_signals", return_value=SAMPLE_CLUSTERS) as mock_cluster,
            patch("src.pipeline.briefing.write_cluster_ids") as mock_write_ids,
            patch("src.pipeline.briefing.generate_briefing_narrative", return_value=SAMPLE_NARRATIVE) as mock_gen,
            patch("src.pipeline.briefing.write_briefing") as mock_write_briefing,
            patch("src.pipeline.briefing.write_briefing_heartbeat") as mock_heartbeat,
            patch("src.pipeline.briefing._run_translator_pipeline"),
        ):
            # No existing heartbeat (first run)
            mock_hb_path.exists.return_value = False

            run_analyst_briefing_pipeline()

        mock_fetch.assert_called_once_with(mock_client)
        mock_history.assert_called_once_with(mock_client, days=7)
        mock_cluster.assert_called_once_with(SAMPLE_SIGNALS, [], mock_client)
        mock_write_ids.assert_called_once_with(mock_client, SAMPLE_CLUSTERS)
        mock_gen.assert_called_once_with(SAMPLE_CLUSTERS, SAMPLE_SIGNALS)
        mock_write_briefing.assert_called_once_with(mock_client, SAMPLE_NARRATIVE, SAMPLE_CLUSTERS)
        mock_heartbeat.assert_called_once_with(
            len(SAMPLE_SIGNALS), len(SAMPLE_CLUSTERS["clusters"])
        )
        mock_client.close.assert_called_once()

    def test_briefing_triggers_translator(self):
        """run_analyst_briefing_pipeline calls _run_translator_pipeline once on success."""
        from src.pipeline.briefing import run_analyst_briefing_pipeline

        mock_client = self._make_pipeline_mocks()

        with (
            patch("src.pipeline.briefing.BRIEFING_HEARTBEAT_PATH") as mock_hb_path,
            patch("src.pipeline.briefing.get_client", return_value=mock_client),
            patch("src.pipeline.briefing.fetch_todays_signals", return_value=SAMPLE_SIGNALS),
            patch("src.pipeline.briefing.fetch_recent_signals", return_value=[]),
            patch("src.pipeline.briefing.cluster_signals", return_value=SAMPLE_CLUSTERS),
            patch("src.pipeline.briefing.write_cluster_ids"),
            patch("src.pipeline.briefing.generate_briefing_narrative", return_value=SAMPLE_NARRATIVE),
            patch("src.pipeline.briefing.write_briefing"),
            patch("src.pipeline.briefing.write_briefing_heartbeat"),
            patch("src.pipeline.briefing._run_translator_pipeline") as mock_translator,
        ):
            mock_hb_path.exists.return_value = False

            run_analyst_briefing_pipeline()

        mock_translator.assert_called_once()

    def test_pipeline_concurrency_guard(self):
        """Returns early if heartbeat shows status=running."""
        from src.pipeline.briefing import run_analyst_briefing_pipeline

        running_heartbeat = json.dumps({"status": "running", "last_run": "2026-03-15T06:00:00Z"})

        with (
            patch("src.pipeline.briefing.BRIEFING_HEARTBEAT_PATH") as mock_hb_path,
            patch("src.pipeline.briefing.get_client") as mock_get_client,
            patch("src.pipeline.briefing.fetch_todays_signals") as mock_fetch,
        ):
            mock_hb_path.exists.return_value = True
            mock_hb_path.read_text.return_value = running_heartbeat

            run_analyst_briefing_pipeline()

        # Should not proceed to pipeline steps
        mock_get_client.assert_not_called()
        mock_fetch.assert_not_called()
