"""Document storage and vector operations service.

The API layer imports from here instead of accessing ``app.infra.minio`` and
``app.infra.qdrant`` directly, preserving the api → services → infra layering.
"""

from __future__ import annotations

import asyncio
import io

import structlog
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.core.config import settings
from app.infra.minio import get_minio_client
from app.infra.qdrant import get_qdrant_client, user_collection_name

logger = structlog.get_logger(__name__)

__all__ = [
    "user_collection_name",
    "upload_file",
    "delete_file",
    "sync_filename_to_vectors",
    "delete_vectors",
]


async def upload_file(content: bytes, object_key: str) -> None:
    """Upload raw bytes to the configured MinIO bucket."""
    client = get_minio_client()
    await asyncio.to_thread(
        client.put_object,
        settings.minio_bucket,
        object_key,
        io.BytesIO(content),
        len(content),
    )


async def delete_file(object_key: str) -> None:
    """Delete an object from MinIO."""
    client = get_minio_client()
    await asyncio.to_thread(
        client.remove_object,
        settings.minio_bucket,
        object_key,
    )


async def sync_filename_to_vectors(collection: str, doc_id: str, filename: str) -> None:
    """Update the filename payload for all vectors belonging to a document."""
    client = await get_qdrant_client()
    await client.set_payload(
        collection_name=collection,
        payload={"filename": filename},
        points=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
    )


async def delete_vectors(collection: str, doc_id: str) -> None:
    """Remove all vectors for a document from Qdrant."""
    client = await get_qdrant_client()
    await client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
    )
