"""FastAPI application entry point for the Meridian pipeline orchestrator."""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from src.api.routes.trigger import router as trigger_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Meridian Pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(trigger_router)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
