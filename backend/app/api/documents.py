import asyncio
import io
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from qdrant_client.models import FieldCondition, Filter, MatchValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ResolvedLLMConfig, get_current_user, get_llm_config
from app.core.config import settings
from app.core.security import resolve_api_key
from app.db.models import Document, User, Workspace, WorkspaceMember
from app.db.session import get_db
from app.infra.minio import get_minio_client
from app.infra.qdrant import get_qdrant_client, user_collection_name
from app.rag.indexer import index_document

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_TYPES = {"pdf", "txt", "md", "docx"}
MAX_SIZE = 50 * 1024 * 1024


def extract_text(content: bytes, file_type: str) -> str:
    match file_type:
        case "txt" | "md":
            return content.decode("utf-8", errors="ignore")
        case "pdf":
            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(content))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        case "docx":
            import docx

            doc = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        case _:
            return ""


@router.get("")
async def list_documents(
    workspace_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[dict]]:
    if workspace_id is not None:
        # Workspace listing: show all docs in this workspace to members.
        ws = await db.get(Workspace, workspace_id)
        if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
            raise HTTPException(status_code=404, detail="Workspace not found")
        membership = await db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user.id,
            )
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Not a workspace member")
        query = (
            select(Document)
            .where(
                Document.workspace_id == workspace_id,
                Document.is_deleted.is_(False),
            )
            .order_by(Document.created_at.desc())
        )
    else:
        # Personal listing: only the user's own non-workspace documents.
        query = (
            select(Document)
            .where(
                Document.user_id == user.id,
                Document.workspace_id.is_(None),
                Document.is_deleted.is_(False),
            )
            .order_by(Document.created_at.desc())
        )
    rows = await db.scalars(query)
    docs = rows.all()
    return {
        "documents": [
            {
                "id": str(d.id),
                "filename": d.filename,
                "file_type": d.file_type,
                "file_size_bytes": d.file_size_bytes,
                "chunk_count": d.chunk_count,
                "created_at": d.created_at.isoformat(),
                "workspace_id": str(d.workspace_id) if d.workspace_id else None,
            }
            for d in docs
        ]
    }


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    doc = await db.get(Document, doc_id)
    if not doc or doc.user_id != user.id or doc.is_deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.is_deleted = True
    doc.chunk_count = 0
    await db.commit()

    # Use the stored collection name so workspace docs are cleaned up correctly.
    collection = doc.qdrant_collection or user_collection_name(str(user.id))
    try:
        q_client = await get_qdrant_client()
        await q_client.delete(
            collection_name=collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=str(doc.id)),
                    )
                ]
            ),
        )
    except Exception:
        logger.exception("qdrant_delete_failed", doc_id=str(doc.id))

    logger.info("document_deleted", user_id=str(user.id), doc_id=str(doc.id))


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    workspace_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    llm: ResolvedLLMConfig = Depends(get_llm_config),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str | int]:
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type .{ext} not supported")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50MB limit")

    # Validate workspace membership before touching MinIO to avoid orphaned objects.
    qdrant_collection = user_collection_name(str(user.id))
    if workspace_id is not None:
        ws = await db.get(Workspace, workspace_id)
        if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
            raise HTTPException(status_code=404, detail="Workspace not found")
        membership = await db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user.id,
            )
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Not a workspace member")
        qdrant_collection = f"workspace_{workspace_id}"

    safe_name = Path(file.filename or "upload").name
    object_key = f"{user.id}/{uuid.uuid4()}_{safe_name}"

    minio_client = get_minio_client()
    await asyncio.to_thread(
        minio_client.put_object,
        settings.minio_bucket,
        object_key,
        io.BytesIO(content),
        len(content),
    )

    text = await asyncio.to_thread(extract_text, content, ext)
    doc = Document(
        user_id=user.id,
        filename=safe_name,
        file_type=ext,
        file_size_bytes=len(content),
        qdrant_collection=qdrant_collection,
        minio_object_key=object_key,
    )
    if workspace_id is not None:
        doc.workspace_id = workspace_id
    db.add(doc)
    await db.flush()
    # Embeddings always use OpenAI (text-embedding-3-small), resolve the
    # OpenAI key regardless of which LLM provider the user has selected.
    openai_key = resolve_api_key("openai", llm.raw_keys)
    if not openai_key:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key is required for document embedding. "
            "Configure it in Settings or ask the admin.",
        )
    chunk_count = await index_document(
        str(user.id),
        str(doc.id),
        text,
        openai_key,
        doc_name=safe_name,
        collection_name=qdrant_collection,
    )
    doc.chunk_count = chunk_count
    await db.commit()
    logger.info(
        "document_uploaded",
        user_id=str(user.id),
        doc_id=str(doc.id),
        filename=doc.filename,
        file_type=ext,
        file_size_bytes=len(content),
        chunk_count=chunk_count,
    )
    return {"id": str(doc.id), "filename": doc.filename, "chunk_count": chunk_count}
