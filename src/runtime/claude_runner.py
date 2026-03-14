"""Claude Code CLI subprocess wrapper for the Meridian pipeline."""

import json
import subprocess


def invoke_claude(
    prompt: str,
    model: str = "claude-sonnet-4-5",
    timeout: int = 120,
) -> dict:
    """Invoke the Claude Code CLI and return parsed JSON output.

    Args:
        prompt: The prompt to send to Claude.
        model: The Claude model to use.
        timeout: Subprocess timeout in seconds.

    Returns:
        Parsed JSON dict with keys: result, model, usage, cost_usd.

    Raises:
        RuntimeError: If the CLI exits with a non-zero return code.
        json.JSONDecodeError: If stdout is not valid JSON.
    """
    result = subprocess.run(
        ["claude", "-p", "--output-format", "json", "--model", model],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Claude CLI exited with code {result.returncode}: {result.stderr}"
        )

    return json.loads(result.stdout)
