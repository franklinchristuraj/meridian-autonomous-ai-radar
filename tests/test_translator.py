"""Unit tests for translator pipeline module."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Schema migration tests
# ---------------------------------------------------------------------------

class TestMigrateSignalsConfidence:
    def test_migrate_signals_confidence(self):
        """Calling _migrate_signals_confidence adds confidence NUMBER property."""
        from src.db.schema import _migrate_signals_confidence

        mock_client = MagicMock()
        mock_client.collections.exists.return_value = True
        mock_signals = MagicMock()
        mock_client.collections.get.return_value = mock_signals

        _migrate_signals_confidence(mock_client)

        mock_signals.config.add_property.assert_called_once()
        call_args = mock_signals.config.add_property.call_args[0][0]
        assert call_args.name == "confidence"

    def test_migrate_signals_confidence_idempotent(self):
        """Calling _migrate_signals_confidence twice does not raise."""
        from src.db.schema import _migrate_signals_confidence

        mock_client = MagicMock()
        mock_client.collections.exists.return_value = True
        mock_signals = MagicMock()
        mock_client.collections.get.return_value = mock_signals
        # Second call raises (property already exists) — should be swallowed
        mock_signals.config.add_property.side_effect = [None, Exception("already exists")]

        _migrate_signals_confidence(mock_client)
        _migrate_signals_confidence(mock_client)  # Should not raise


# ---------------------------------------------------------------------------
# fetch_vault_signals tests
# ---------------------------------------------------------------------------

class TestFetchVaultSignals:
    def _make_signal_obj(self, confidence, uuid_str="uuid-1", title="Test Paper"):
        obj = MagicMock()
        obj.uuid = uuid_str
        obj.properties = {
            "title": title,
            "abstract": "Abstract text",
            "source_url": "http://arxiv.org/abs/2401.12345",
            "score": 8.5,
            "confidence": confidence,
            "matched_pattern_ids": ["pat-001"],
            "cluster_id": "cluster_001",
        }
        return obj

    def test_fetch_vault_signals_filters_confidence(self):
        """Returns only signals with confidence >= 0.8."""
        from src.pipeline.translator import fetch_vault_signals

        high = self._make_signal_obj(0.9, "uuid-1")
        low = self._make_signal_obj(0.5, "uuid-2")
        none_conf = self._make_signal_obj(None, "uuid-3")

        mock_client = MagicMock()
        mock_col = MagicMock()
        mock_client.collections.get.return_value = mock_col
        mock_response = MagicMock()
        mock_response.objects = [high, low, none_conf]
        mock_col.query.fetch_objects.return_value = mock_response

        results = fetch_vault_signals(mock_client)

        assert len(results) == 1
        assert results[0]["uuid"] == "uuid-1"

    def test_fetch_vault_signals_returns_expected_keys(self):
        """Returned dicts contain required keys."""
        from src.pipeline.translator import fetch_vault_signals

        obj = self._make_signal_obj(0.9)

        mock_client = MagicMock()
        mock_col = MagicMock()
        mock_client.collections.get.return_value = mock_col
        mock_response = MagicMock()
        mock_response.objects = [obj]
        mock_col.query.fetch_objects.return_value = mock_response

        results = fetch_vault_signals(mock_client)

        assert len(results) == 1
        keys = results[0].keys()
        for expected in ["uuid", "title", "abstract", "source_url", "score", "confidence",
                         "matched_pattern_ids", "cluster_id"]:
            assert expected in keys, f"Missing key: {expected}"


# ---------------------------------------------------------------------------
# rank_and_cap tests
# ---------------------------------------------------------------------------

class TestRankAndCap:
    def test_rank_and_cap_sorts_descending(self):
        """Signals sorted by confidence descending."""
        from src.pipeline.translator import rank_and_cap

        signals = [
            {"confidence": 0.85, "title": "A"},
            {"confidence": 0.95, "title": "B"},
            {"confidence": 0.80, "title": "C"},
        ]
        result = rank_and_cap(signals, max_n=10)
        confidences = [s["confidence"] for s in result]
        assert confidences == [0.95, 0.85, 0.80]

    def test_rank_and_cap_limits_to_max_n(self):
        """Returns exactly max_n signals when more are provided."""
        from src.pipeline.translator import rank_and_cap

        signals = [{"confidence": 0.9 - i * 0.01} for i in range(5)]
        result = rank_and_cap(signals, max_n=3)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# _load_deposited_urls tests
# ---------------------------------------------------------------------------

class TestLoadDepositedUrls:
    def test_load_deposited_urls_finds_arxiv(self, tmp_path):
        """Extracts arxiv_url from frontmatter."""
        from src.pipeline.translator import _load_deposited_urls

        seed_file = tmp_path / "some-paper.md"
        seed_file.write_text(
            "---\narxiv_url: http://arxiv.org/abs/2401.12345\ntitle: Some Paper\n---\n\n# Body"
        )

        result = _load_deposited_urls(tmp_path)
        assert result == {"http://arxiv.org/abs/2401.12345"}

    def test_load_deposited_urls_skips_corrupt(self, tmp_path):
        """Returns empty set for file with no frontmatter — no raise."""
        from src.pipeline.translator import _load_deposited_urls

        bad_file = tmp_path / "corrupt.md"
        bad_file.write_text("No frontmatter here, just body text.")

        result = _load_deposited_urls(tmp_path)
        assert result == set()

    def test_load_deposited_urls_empty_dir(self, tmp_path):
        """Returns empty set when directory has no .md files."""
        from src.pipeline.translator import _load_deposited_urls

        result = _load_deposited_urls(tmp_path)
        assert result == set()


# ---------------------------------------------------------------------------
# render_seed_note tests
# ---------------------------------------------------------------------------

SAMPLE_SIGNAL = {
    "uuid": "test-uuid-123",
    "title": "Multi-Agent Orchestration Framework",
    "abstract": "We propose a novel multi-agent orchestration framework for distributed AI systems.",
    "source_url": "http://arxiv.org/abs/2401.12345",
    "score": 8.5,
    "confidence": 0.92,
    "matched_pattern_ids": ["AGENTIC-01", "AGENTIC-02"],
    "cluster_id": "cluster_001",
}


class TestRenderSeedNote:
    def test_render_seed_note_frontmatter(self):
        """Output contains all required frontmatter fields."""
        from src.pipeline.translator import render_seed_note

        output = render_seed_note(SAMPLE_SIGNAL)

        assert 'folder: "01_seeds"' in output
        assert 'type: "seed"' in output
        assert 'status: "raw"' in output
        assert 'urgency: "low"' in output
        assert 'context: "work"' in output
        assert 'source: "meridian"' in output
        assert 'spark_stage: "capture"' in output
        assert "tags: [seed, auto-deposit]" in output
        assert "auto_deposit: true" in output
        assert "test-uuid-123" in output
        assert "0.92" in output
        assert "8.5" in output
        assert "AGENTIC-01" in output
        assert "http://arxiv.org/abs/2401.12345" in output

    def test_render_seed_note_body(self):
        """Output contains H1 title and abstract text."""
        from src.pipeline.translator import render_seed_note

        output = render_seed_note(SAMPLE_SIGNAL)

        assert "# Multi-Agent Orchestration Framework" in output
        assert "We propose a novel multi-agent orchestration framework" in output

    def test_render_seed_note_agent_context(self):
        """agent_context field contains required text."""
        from src.pipeline.translator import render_seed_note

        output = render_seed_note(SAMPLE_SIGNAL)

        assert "Auto-deposited VAULT signal from Meridian" in output


# ---------------------------------------------------------------------------
# slugify_title tests
# ---------------------------------------------------------------------------

class TestSlugifyTitle:
    def test_slugify_basic(self):
        from src.pipeline.translator import slugify_title
        assert slugify_title("Multi-Agent Orchestration Framework") == "multi-agent-orchestration-framework"

    def test_slugify_special_chars(self):
        from src.pipeline.translator import slugify_title
        assert slugify_title("On X: A Study (2024)") == "on-x-a-study-2024"

    def test_slugify_strips_edges(self):
        from src.pipeline.translator import slugify_title
        assert slugify_title("---hello---") == "hello"


# ---------------------------------------------------------------------------
# get_vault_seeds_path tests
# ---------------------------------------------------------------------------

class TestGetVaultSeedsPath:
    def test_vault_path_not_set(self, monkeypatch):
        """Raises EnvironmentError when OBSIDIAN_VAULT_PATH not in env."""
        from src.pipeline.translator import get_vault_seeds_path

        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)

        with pytest.raises(EnvironmentError):
            get_vault_seeds_path()

    def test_vault_path_missing_dir(self, monkeypatch, tmp_path):
        """Raises FileNotFoundError when 01_seeds/ doesn't exist."""
        from src.pipeline.translator import get_vault_seeds_path

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        # Do NOT create 01_seeds/

        with pytest.raises(FileNotFoundError):
            get_vault_seeds_path()

    def test_vault_path_valid(self, monkeypatch, tmp_path):
        """Returns Path to 01_seeds/ when properly configured."""
        from src.pipeline.translator import get_vault_seeds_path

        seeds_dir = tmp_path / "01_seeds"
        seeds_dir.mkdir()
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

        result = get_vault_seeds_path()
        assert result == seeds_dir


# ---------------------------------------------------------------------------
# write_translator_heartbeat tests
# ---------------------------------------------------------------------------

class TestWriteTranslatorHeartbeat:
    def test_heartbeat_writes_json(self):
        """Writes heartbeat/translator.json with required keys."""
        from src.pipeline.translator import write_translator_heartbeat, TRANSLATOR_HEARTBEAT_PATH

        mock_path = MagicMock()
        mock_path.parent = MagicMock()

        with patch("src.pipeline.translator.TRANSLATOR_HEARTBEAT_PATH", mock_path):
            write_translator_heartbeat(deposited=2)

        mock_path.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_path.write_text.assert_called_once()

        written_text = mock_path.write_text.call_args[0][0]
        written_data = json.loads(written_text)

        assert "last_run" in written_data
        assert written_data["seeds_deposited"] == 2
        assert written_data["status"] == "ok"


# ---------------------------------------------------------------------------
# run_translator_pipeline tests
# ---------------------------------------------------------------------------

def _make_signal(uuid_str, url, confidence=0.9, title="Test Paper"):
    return {
        "uuid": uuid_str,
        "title": title,
        "abstract": "Abstract text for " + title,
        "source_url": url,
        "score": 8.0,
        "confidence": confidence,
        "matched_pattern_ids": ["AGENTIC-01"],
        "cluster_id": "cluster_001",
    }


class TestRunTranslatorPipeline:
    def test_pipeline_happy_path(self, tmp_path):
        """With 2 qualifying signals, writes 2 .md files and heartbeat shows seeds_deposited=2."""
        from src.pipeline.translator import run_translator_pipeline

        seeds_dir = tmp_path / "01_seeds"
        seeds_dir.mkdir()

        signals = [
            _make_signal("uuid-1", "http://arxiv.org/abs/1", title="Paper One"),
            _make_signal("uuid-2", "http://arxiv.org/abs/2", title="Paper Two"),
        ]

        mock_client = MagicMock()
        mock_hb_path = MagicMock()
        mock_hb_path.parent = MagicMock()

        with (
            patch("src.pipeline.translator.get_vault_seeds_path", return_value=seeds_dir),
            patch("src.pipeline.translator.get_client", return_value=mock_client),
            patch("src.pipeline.translator.fetch_vault_signals", return_value=signals),
            patch("src.pipeline.translator.rank_and_cap", return_value=signals),
            patch("src.pipeline.translator.TRANSLATOR_HEARTBEAT_PATH", mock_hb_path),
        ):
            run_translator_pipeline()

        md_files = list(seeds_dir.glob("*.md"))
        assert len(md_files) == 2
        mock_client.close.assert_called_once()

        written_text = mock_hb_path.write_text.call_args[0][0]
        hb_data = json.loads(written_text)
        assert hb_data["seeds_deposited"] == 2

    def test_pipeline_swallows_runtime_errors(self, tmp_path):
        """When runtime error raised inside try block, pipeline logs and does NOT raise."""
        from src.pipeline.translator import run_translator_pipeline

        seeds_dir = tmp_path / "01_seeds"
        seeds_dir.mkdir()

        mock_client = MagicMock()

        with (
            patch("src.pipeline.translator.get_vault_seeds_path", return_value=seeds_dir),
            patch("src.pipeline.translator.get_client", return_value=mock_client),
            patch("src.pipeline.translator.fetch_vault_signals", side_effect=OSError("disk error")),
        ):
            # Should NOT raise
            run_translator_pipeline()

        mock_client.close.assert_called_once()

    def test_pipeline_skips_duplicates(self, tmp_path):
        """With 2 signals where 1 arxiv_url already in seeds dir, writes only 1 new file."""
        from src.pipeline.translator import run_translator_pipeline

        seeds_dir = tmp_path / "01_seeds"
        seeds_dir.mkdir()

        # Pre-existing seed with url-1 already deposited
        existing = seeds_dir / "paper-one.md"
        existing.write_text(
            "---\narxiv_url: http://arxiv.org/abs/1\ntitle: Paper One\n---\n\n# Paper One"
        )

        signals = [
            _make_signal("uuid-1", "http://arxiv.org/abs/1", title="Paper One"),
            _make_signal("uuid-2", "http://arxiv.org/abs/2", title="Paper Two"),
        ]

        mock_client = MagicMock()
        mock_hb_path = MagicMock()
        mock_hb_path.parent = MagicMock()

        with (
            patch("src.pipeline.translator.get_vault_seeds_path", return_value=seeds_dir),
            patch("src.pipeline.translator.get_client", return_value=mock_client),
            patch("src.pipeline.translator.fetch_vault_signals", return_value=signals),
            patch("src.pipeline.translator.rank_and_cap", return_value=signals),
            patch("src.pipeline.translator.TRANSLATOR_HEARTBEAT_PATH", mock_hb_path),
        ):
            run_translator_pipeline()

        # Only 1 new file (not counting the existing one)
        all_md = list(seeds_dir.glob("*.md"))
        # existing + 1 new = 2 total
        assert len(all_md) == 2
        # But deposited count should be 1
        written_text = mock_hb_path.write_text.call_args[0][0]
        hb_data = json.loads(written_text)
        assert hb_data["seeds_deposited"] == 1

    def test_daily_cap_enforced(self, tmp_path):
        """With 5 qualifying signals, writes exactly 3 (cap)."""
        from src.pipeline.translator import run_translator_pipeline

        seeds_dir = tmp_path / "01_seeds"
        seeds_dir.mkdir()

        signals = [
            _make_signal(f"uuid-{i}", f"http://arxiv.org/abs/{i}", title=f"Paper {i}")
            for i in range(5)
        ]
        # rank_and_cap already limits to 3 — but pipeline also enforces cap internally
        capped = signals[:3]

        mock_client = MagicMock()
        mock_hb_path = MagicMock()
        mock_hb_path.parent = MagicMock()

        with (
            patch("src.pipeline.translator.get_vault_seeds_path", return_value=seeds_dir),
            patch("src.pipeline.translator.get_client", return_value=mock_client),
            patch("src.pipeline.translator.fetch_vault_signals", return_value=signals),
            patch("src.pipeline.translator.rank_and_cap", return_value=capped),
            patch("src.pipeline.translator.TRANSLATOR_HEARTBEAT_PATH", mock_hb_path),
        ):
            run_translator_pipeline()

        md_files = list(seeds_dir.glob("*.md"))
        assert len(md_files) == 3

    def test_pipeline_slug_collision(self, tmp_path):
        """When two signals produce the same slug, second gets -2 suffix."""
        from src.pipeline.translator import run_translator_pipeline

        seeds_dir = tmp_path / "01_seeds"
        seeds_dir.mkdir()

        # Two signals with same title -> same slug
        signals = [
            _make_signal("uuid-1", "http://arxiv.org/abs/1", title="Duplicate Title"),
            _make_signal("uuid-2", "http://arxiv.org/abs/2", title="Duplicate Title"),
        ]

        mock_client = MagicMock()
        mock_hb_path = MagicMock()
        mock_hb_path.parent = MagicMock()

        with (
            patch("src.pipeline.translator.get_vault_seeds_path", return_value=seeds_dir),
            patch("src.pipeline.translator.get_client", return_value=mock_client),
            patch("src.pipeline.translator.fetch_vault_signals", return_value=signals),
            patch("src.pipeline.translator.rank_and_cap", return_value=signals),
            patch("src.pipeline.translator.TRANSLATOR_HEARTBEAT_PATH", mock_hb_path),
        ):
            run_translator_pipeline()

        md_files = sorted(seeds_dir.glob("*.md"))
        filenames = [f.name for f in md_files]
        assert "duplicate-title.md" in filenames
        assert "duplicate-title-2.md" in filenames
