"""Tests for the Claude Code CLI subprocess wrapper."""

import json
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from src.runtime.claude_runner import invoke_claude


MOCK_SUCCESS_STDOUT = json.dumps({
    "result": "test output",
    "model": "claude-sonnet-4-5",
    "usage": {"input_tokens": 10, "output_tokens": 20},
    "cost_usd": 0.001,
})


def test_invoke_claude_returns_parsed_json():
    """Mocked subprocess returns valid JSON; invoke_claude parses it correctly."""
    mock_result = CompletedProcess(
        args=["claude"],
        returncode=0,
        stdout=MOCK_SUCCESS_STDOUT,
        stderr="",
    )
    with patch("src.runtime.claude_runner.subprocess.run", return_value=mock_result) as mock_run:
        result = invoke_claude("test prompt")

    assert result["result"] == "test output"
    assert result["model"] == "claude-sonnet-4-5"
    assert result["usage"]["input_tokens"] == 10
    assert result["cost_usd"] == 0.001
    mock_run.assert_called_once()


def test_invoke_claude_raises_on_nonzero_exit():
    """Mocked subprocess returns returncode=1; invoke_claude raises RuntimeError."""
    mock_result = CompletedProcess(
        args=["claude"],
        returncode=1,
        stdout="",
        stderr="error message from claude",
    )
    with patch("src.runtime.claude_runner.subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError) as exc_info:
            invoke_claude("test prompt")

    assert "error message from claude" in str(exc_info.value)


def test_invoke_claude_raises_on_invalid_json():
    """Mocked subprocess returns non-JSON stdout; invoke_claude raises ValueError or JSONDecodeError."""
    mock_result = CompletedProcess(
        args=["claude"],
        returncode=0,
        stdout="not valid json at all",
        stderr="",
    )
    with patch("src.runtime.claude_runner.subprocess.run", return_value=mock_result):
        with pytest.raises((json.JSONDecodeError, ValueError)):
            invoke_claude("test prompt")


class TestInvokeClaudeSpan:
    """OBS-02: invoke_claude() creates span with LLM attributes."""

    @patch("src.runtime.claude_runner.subprocess.run")
    def test_invoke_claude_creates_llm_span(self, mock_run, otel_test_provider):
        mock_run.return_value = CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout=json.dumps({
                "result": "test output",
                "model": "claude-sonnet-4-5",
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "cost_usd": 0.003,
            }),
            stderr="",
        )

        invoke_claude("test prompt", model="claude-sonnet-4-5")

        spans = otel_test_provider.get_finished_spans()
        llm_spans = [s for s in spans if s.name == "invoke_claude"]
        assert len(llm_spans) == 1
        attrs = dict(llm_spans[0].attributes)
        assert attrs["llm.model_name"] == "claude-sonnet-4-5"
        assert attrs["llm.token_count.prompt"] == 100
        assert attrs["llm.token_count.completion"] == 50
        assert attrs["llm.token_count.total"] == 150
        assert attrs["llm.cost_usd"] == 0.003
        assert "test prompt" in attrs["input.value"]
        assert "test output" in attrs["output.value"]
