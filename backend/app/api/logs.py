"""Client-side error reporting endpoint."""

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])


class ClientError(BaseModel):
    message: str
    source: str | None = None
    trace_id: str | None = None
    url: str | None = None
    stack: str | None = None


@router.post("/client-error", status_code=204)
async def report_client_error(body: ClientError) -> None:
    """Accept and log client-side errors. No auth required."""
    logger.warning(
        "client_error",
        message=body.message[:500],
        source=body.source,
        trace_id=body.trace_id,
        url=body.url,
    )
