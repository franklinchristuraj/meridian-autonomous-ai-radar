"""Centralized OpenTelemetry tracer initialization for the Meridian pipeline.

Call init_tracing() once at application startup (FastAPI lifespan).
All pipeline modules use trace.get_tracer() to obtain a live tracer —
no need to pass tracer objects through the call chain.
"""

import logging
import os

from opentelemetry import trace
from opentelemetry.trace import StatusCode  # re-export for convenience

logger = logging.getLogger(__name__)

# Module-level tracer — becomes live after init_tracing() is called.
# Before init_tracing(), this is a no-op tracer (safe to import early).
tracer = trace.get_tracer("meridian.pipeline")


def init_tracing(
    endpoint: str | None = None,
    project_name: str = "meridian",
) -> None:
    """Initialize the global TracerProvider via Phoenix OTEL register().

    Args:
        endpoint: Phoenix collector URL (e.g. "http://host:6006/v1/traces").
                  Falls back to PHOENIX_COLLECTOR_ENDPOINT env var,
                  then "http://localhost:6006/v1/traces".
        project_name: Project name shown in Phoenix UI.

    Auth: If PHOENIX_API_KEY is set, it's passed as an authorization header
    to the Phoenix collector. Required when Phoenix has auth enabled.

    This MUST be called before any spans are created (i.e., before
    APScheduler starts or any pipeline runs).
    """
    resolved_endpoint = (
        endpoint
        or os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
        or "http://localhost:6006/v1/traces"
    )

    api_key = os.getenv("PHOENIX_API_KEY")
    headers = {"authorization": api_key} if api_key else None

    try:
        from phoenix.otel import register

        register(
            endpoint=resolved_endpoint,
            project_name=project_name,
            headers=headers,
            batch=True,
        )
        logger.info(
            "Tracing initialized: endpoint=%s project=%s",
            resolved_endpoint,
            project_name,
        )
    except Exception as e:
        logger.warning(
            "Failed to initialize Phoenix tracing (traces will be no-op): %s", e
        )
