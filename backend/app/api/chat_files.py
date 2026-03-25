"""Stateless file text extraction for chat file attachments."""

from __future__ import annotations

import io

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.db.models import User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_TEXT_CHARS = 30_000

_ALLOWED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "text/markdown",
}


class ExtractFileResponse(BaseModel):
    filename: str
    char_count: int
    extracted_text: str


@router.post("/extract-file", response_model=ExtractFileResponse)
@limiter.limit("10/minute")
async def extract_file(
    request: Request,
    file: UploadFile,
    _user: User = Depends(get_current_user),
) -> ExtractFileResponse:
    """Extract text from an uploaded file (PDF, DOCX, TXT, CSV, MD)."""
    content_type = file.content_type or ""
    # Normalise text/* subtypes
    if content_type.startswith("text/"):
        content_type = content_type.split(";")[0].strip()

    if content_type not in _ALLOWED_MIMES:
        allowed_str = ", ".join(["PDF", "DOCX", "TXT", "CSV", "MD"])
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {content_type}. Allowed: {allowed_str}",
        )

    raw = await file.read()
    if len(raw) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    try:
        text = _extract(content_type, raw)
    except Exception as exc:
        logger.warning("file_extraction_failed", filename=file.filename, exc_info=True)
        raise HTTPException(
            status_code=422, detail=f"Extraction failed: {exc}"
        ) from exc

    truncated = text[:_MAX_TEXT_CHARS]
    return ExtractFileResponse(
        filename=file.filename or "attachment",
        char_count=len(truncated),
        extracted_text=truncated,
    )


def _extract(content_type: str, raw: bytes) -> str:
    if content_type == "application/pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if (
        content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        from docx import Document

        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)

    # TXT / CSV / MD
    return raw.decode("utf-8", errors="replace")
