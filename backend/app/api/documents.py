import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from minio import Minio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models import Document, User, UserSettings
from app.db.session import get_db
from app.rag.indexer import index_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_TYPES = {"pdf", "txt", "md", "docx"}
MAX_SIZE = 50 * 1024 * 1024


def extract_text(content: bytes, file_type: str) -> str:
    if file_type in ("txt", "md"):
        return content.decode("utf-8", errors="ignore")
    if file_type == "pdf":
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    if file_type == "docx":
        import docx

        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    return ""


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type .{ext} not supported")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50MB limit")

    minio_client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
    if not minio_client.bucket_exists(settings.minio_bucket):
        minio_client.make_bucket(settings.minio_bucket)
    object_key = f"{user.id}/{file.filename}"
    minio_client.put_object(
        settings.minio_bucket,
        object_key,
        io.BytesIO(content),
        len(content),
    )

    user_settings = await db.scalar(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    api_key = (
        (user_settings.api_keys or {}).get(user_settings.model_provider, "")
        if user_settings
        else ""
    )

    text = extract_text(content, ext)
    doc = Document(
        user_id=user.id,
        filename=file.filename,
        file_type=ext,
        file_size_bytes=len(content),
        qdrant_collection=f"user_{user.id}",
        minio_object_key=object_key,
    )
    db.add(doc)
    await db.flush()
    chunk_count = await index_document(str(user.id), str(doc.id), text, api_key)
    doc.chunk_count = chunk_count
    await db.commit()
    return {"id": str(doc.id), "filename": doc.filename, "chunk_count": chunk_count}
