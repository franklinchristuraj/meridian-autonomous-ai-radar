"""Pipeline trigger endpoint — accepts manual seed payloads."""

import logging

from fastapi import APIRouter, BackgroundTasks, Security
from pydantic import BaseModel

from src.api.auth import verify_api_key
from src.pipeline.ingest import ingest_manual_seed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class SeedPayload(BaseModel):
    title: str
    url: str | None = None
    notes: str | None = None
    abstract: str | None = None


@router.post("/trigger", status_code=202)
async def trigger_pipeline(
    payload: SeedPayload,
    background_tasks: BackgroundTasks,
    _key: str = Security(verify_api_key),
) -> dict:
    """Accept a manual seed payload and enqueue ingestion in the background."""
    background_tasks.add_task(ingest_manual_seed, payload.model_dump())
    return {"status": "accepted"}
