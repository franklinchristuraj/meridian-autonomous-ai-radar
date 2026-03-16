"""Claude Code CLI subprocess wrapper for the Meridian pipeline."""

import json
import subprocess

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from openinference.semconv.trace import SpanAttributes

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
    with trace.get_tracer("meridian.llm").start_as_current_span("invoke_claude") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "LLM")
        span.set_attribute(SpanAttributes.LLM_MODEL_NAME, model)
        # Truncate input to 32KB to avoid OTLP export size issues
        span.set_attribute(SpanAttributes.INPUT_VALUE, prompt[:32768])
        if len(prompt) > 32768:
            span.set_attribute("input.truncated", True)

        try:
            result = subprocess.run(
                ["claude", "-p", "--output-format", "json", "--model", model],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                error = RuntimeError(
                    f"Claude CLI exited with code {result.returncode}: {result.stderr}"
                )
                span.record_exception(error)
                span.set_status(StatusCode.ERROR, str(error))
                raise error

            parsed = json.loads(result.stdout)

            # Record LLM-specific attributes from response
            usage = parsed.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_PROMPT, input_tokens)
            span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_COMPLETION, output_tokens)
            span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_TOTAL, input_tokens + output_tokens)
            span.set_attribute("llm.cost_usd", parsed.get("cost_usd", 0.0))

            # Truncate output to 32KB
            output_text = parsed.get("result", "")
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, output_text[:32768])
            if len(output_text) > 32768:
                span.set_attribute("output.truncated", True)

            span.set_status(StatusCode.OK)
            return parsed

        except Exception as e:
            if not span.is_recording():
                pass  # Already handled above for RuntimeError
            else:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
            raise
