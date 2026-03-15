"""Pipeline trigger endpoint."""

import logging

from fastapi import APIRouter, BackgroundTasks, Security

from src.api.auth import verify_api_key
from src.pipeline.scout import run_scout_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/trigger", status_code=202)
async def trigger_pipeline(
    background_tasks: BackgroundTasks,
    _key: str = Security(verify_api_key),
) -> dict:
    """Accept a pipeline trigger request and enqueue execution in the background."""
    background_tasks.add_task(run_scout_pipeline)
    return {"status": "accepted"}
