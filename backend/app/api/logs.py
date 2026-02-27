"""Client-side error reporting endpoint."""

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.core.limiter import limiter

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])


class ClientError(BaseModel):
    message: str = Field(max_length=500)
    source: str | None = Field(default=None, max_length=500)
    trace_id: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=500)
    stack: str | None = Field(default=None, max_length=5000)


@router.post("/client-error", status_code=204)
@limiter.limit("10/minute")
async def report_client_error(request: Request, body: ClientError) -> None:
    """Accept and log client-side errors. No auth required."""
    logger.warning(
        "client_error",
        message=body.message,
        source=body.source,
        trace_id=body.trace_id,
        url=body.url,
    )
