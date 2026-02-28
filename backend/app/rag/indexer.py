import uuid

from qdrant_client.models import PointStruct

from app.infra.qdrant import (
    ensure_user_collection,
    get_qdrant_client,
    user_collection_name,
)
from app.rag.chunker import chunk_text
from app.rag.embedder import get_embedder


async def index_document(
    user_id: str, doc_id: str, text: str, api_key: str, doc_name: str = ""
) -> int:
    """将文档切片、向量化并写入 Qdrant。返回切片数量。"""
    await ensure_user_collection(user_id)
    client = await get_qdrant_client()
    collection = user_collection_name(user_id)

    chunks = chunk_text(text)
    embedder = get_embedder(api_key)
    vectors = await embedder.aembed_documents(chunks)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={
                "doc_id": doc_id,
                "chunk_index": i,
                "text": chunk,
                "doc_name": doc_name,
            },
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors, strict=True))
    ]
    await client.upsert(collection_name=collection, points=points)
    return len(chunks)
