"""API key authentication dependency for FastAPI."""

import os

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: str | None = Security(api_key_header)) -> str:
    """Validate the X-API-Key header against the X_API_KEY environment variable."""
    expected = os.environ.get("X_API_KEY", "")
    if not key or not expected or key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )
    return key
