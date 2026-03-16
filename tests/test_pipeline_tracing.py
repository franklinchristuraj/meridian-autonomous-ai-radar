"""Tests for pipeline tracing instrumentation — OBS-03, OBS-04, OBS-05."""

import json
from unittest.mock import patch, MagicMock

from opentelemetry.trace import StatusCode


class TestScoutSpan:
    """OBS-04: Scout stage span records correct business metric attributes."""

    @patch("src.pipeline.scout.get_client")
    @patch("src.pipeline.scout.fetch_arxiv_papers")
    @patch("src.pipeline.scout.fetch_pattern_keywords")
    @patch("src.pipeline.scout.keyword_filter")
    @patch("src.pipeline.scout._run_briefing_pipeline")
    def test_scout_span_attributes(
        self,
        mock_briefing,
        mock_filter,
        mock_keywords,
        mock_fetch,
        mock_client,
        otel_test_provider,
    ):
        mock_client.return_value = MagicMock()
        mock_fetch.return_value = []
        mock_keywords.return_value = []
        mock_filter.return_value = []

        from src.pipeline.scout import run_scout_pipeline
        run_scout_pipeline()

        spans = otel_test_provider.get_finished_spans()
        scout_spans = [s for s in spans if s.name == "meridian.stage.scout"]
        assert len(scout_spans) == 1
        attrs = dict(scout_spans[0].attributes)
        assert "scout.papers_fetched" in attrs
        assert attrs["scout.papers_fetched"] == 0
        assert "scout.signals_scored" in attrs

    @patch("src.pipeline.scout.get_client")
    @patch("src.pipeline.scout.fetch_arxiv_papers")
    def test_scout_span_error(
        self,
        mock_fetch,
        mock_client,
        otel_test_provider,
    ):
        """OBS-05: Scout span records exception on failure."""
        mock_client.return_value = MagicMock()
        mock_fetch.side_effect = RuntimeError("ArXiv down")

        from src.pipeline.scout import run_scout_pipeline
        try:
            run_scout_pipeline()
        except RuntimeError:
            pass

        spans = otel_test_provider.get_finished_spans()
        scout_spans = [s for s in spans if s.name == "meridian.stage.scout"]
        assert len(scout_spans) == 1
        assert scout_spans[0].status.status_code == StatusCode.ERROR


class TestAnalystSpan:
    """OBS-04: Analyst stage span records cluster count."""

    @patch("src.pipeline.analyst.invoke_claude")
    def test_analyst_span_attributes(
        self,
        mock_claude,
        otel_test_provider,
    ):
        mock_claude.return_value = {
            "result": json.dumps({
                "clusters": [
                    {"cluster_id": "c1", "theme_summary": "test", "signal_ids": ["a"], "matched_pattern_ids": [], "trend_annotation": None}
                ],
                "singletons": []
            })
        }

        from src.pipeline.analyst import cluster_signals
        result = cluster_signals(
            signals=[{"uuid": "a", "title": "t", "tier": "BRIEF", "score": 8, "matched_pattern_ids": [], "reasoning": "r"}],
            history=[],
            client=MagicMock(),
        )

        spans = otel_test_provider.get_finished_spans()
        analyst_spans = [s for s in spans if s.name == "meridian.stage.analyst"]
        assert len(analyst_spans) == 1
        attrs = dict(analyst_spans[0].attributes)
        assert attrs["analyst.clusters_found"] == 1
        assert attrs["analyst.signals_count"] == 1


class TestBriefingSpan:
    """OBS-04: Briefing stage span records signals and clusters."""

    @patch("src.pipeline.briefing.get_client")
    @patch("src.pipeline.briefing.fetch_todays_signals")
    @patch("src.pipeline.briefing.fetch_recent_signals")
    @patch("src.pipeline.briefing.cluster_signals")
    @patch("src.pipeline.briefing.write_cluster_ids")
    @patch("src.pipeline.briefing.generate_briefing_narrative")
    @patch("src.pipeline.briefing.write_briefing")
    @patch("src.pipeline.briefing._run_translator_pipeline")
    @patch("src.pipeline.briefing.BRIEFING_HEARTBEAT_PATH")
    def test_briefing_span_attributes(
        self,
        mock_hb_path,
        mock_translator,
        mock_write_briefing,
        mock_narrative,
        mock_write_clusters,
        mock_cluster,
        mock_history,
        mock_signals,
        mock_client,
        otel_test_provider,
    ):
        mock_hb_path.exists.return_value = False
        mock_hb_path.parent.mkdir = MagicMock()
        mock_hb_path.write_text = MagicMock()
        mock_client.return_value = MagicMock()
        mock_signals.return_value = [{"uuid": "s1"}]
        mock_history.return_value = []
        mock_cluster.return_value = {"clusters": [{"cluster_id": "c1"}], "singletons": []}
        mock_narrative.return_value = {"executive_summary": "test", "items": [{"tier": "BRIEF"}]}

        from src.pipeline.briefing import run_analyst_briefing_pipeline
        run_analyst_briefing_pipeline()

        spans = otel_test_provider.get_finished_spans()
        briefing_spans = [s for s in spans if s.name == "meridian.stage.briefing"]
        assert len(briefing_spans) == 1
        attrs = dict(briefing_spans[0].attributes)
        assert attrs["briefing.signals_processed"] == 1
        assert attrs["briefing.clusters_generated"] == 1


class TestTranslatorSpan:
    """OBS-04: Translator stage span records seeds deposited."""

    @patch("src.pipeline.translator.get_client")
    @patch("src.pipeline.translator.get_vault_seeds_path")
    @patch("src.pipeline.translator.fetch_vault_signals")
    @patch("src.pipeline.translator.write_translator_heartbeat")
    def test_translator_span_attributes(
        self,
        mock_heartbeat,
        mock_fetch,
        mock_vault_path,
        mock_client,
        otel_test_provider,
    ):
        mock_client.return_value = MagicMock()
        mock_vault_path.return_value = MagicMock()
        mock_fetch.return_value = []

        from src.pipeline.translator import run_translator_pipeline
        run_translator_pipeline()

        spans = otel_test_provider.get_finished_spans()
        translator_spans = [s for s in spans if s.name == "meridian.stage.translator"]
        assert len(translator_spans) == 1
        attrs = dict(translator_spans[0].attributes)
        assert attrs["translator.seeds_deposited"] == 0


class TestHeartbeatRegression:
    """OBS-06: Existing heartbeat files still written after instrumentation."""

    @patch("src.pipeline.scout.get_client")
    @patch("src.pipeline.scout.fetch_arxiv_papers")
    @patch("src.pipeline.scout.fetch_pattern_keywords")
    @patch("src.pipeline.scout.keyword_filter")
    @patch("src.pipeline.scout._run_briefing_pipeline")
    @patch("src.pipeline.scout.HEARTBEAT_PATH")
    def test_scout_heartbeat_still_written(
        self,
        mock_hb_path,
        mock_briefing,
        mock_filter,
        mock_keywords,
        mock_fetch,
        mock_client,
        otel_test_provider,
    ):
        mock_hb_path.parent.mkdir = MagicMock()
        mock_hb_path.write_text = MagicMock()
        mock_client.return_value = MagicMock()
        mock_fetch.return_value = []
        mock_keywords.return_value = []
        mock_filter.return_value = []

        from src.pipeline.scout import run_scout_pipeline
        run_scout_pipeline()

        # Heartbeat write_text was called (heartbeat still works)
        mock_hb_path.write_text.assert_called_once()
