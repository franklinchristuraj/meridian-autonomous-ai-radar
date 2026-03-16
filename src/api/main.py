"""FastAPI application entry point for the Meridian pipeline orchestrator."""

import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI

from src.api.routes.briefing import router as briefing_router
from src.api.routes.trigger import router as trigger_router
from src.api.routes.vault import router as vault_router
from src.pipeline.scout import run_scout_pipeline
from src.runtime.tracer import init_tracing

load_dotenv()

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    # Initialize OpenTelemetry tracing BEFORE scheduler starts
    # (ensures TracerProvider is set before any spans are created)
    init_tracing()

    # Startup: schedule Scout daily cron
    cron_hour = int(os.getenv("SCOUT_CRON_HOUR", "6"))
    cron_minute = int(os.getenv("SCOUT_CRON_MINUTE", "0"))
    scheduler.add_job(
        run_scout_pipeline,
        "cron",
        hour=cron_hour,
        minute=cron_minute,
        id="scout_daily",
        replace_existing=True,
    )
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Meridian Pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(trigger_router)
app.include_router(briefing_router)
app.include_router(vault_router)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
