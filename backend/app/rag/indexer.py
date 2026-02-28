import uuid

from qdrant_client.models import PointStruct

from app.infra.qdrant import (
    ensure_user_collection,
    get_qdrant_client,
    user_collection_name,
)
from app.rag.chunker import chunk_text
from app.rag.embedder import get_embedder


async def index_document(user_id: str, doc_id: str, text: str, api_key: str) -> int:
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
            payload={"doc_id": doc_id, "chunk_index": i, "text": chunk},
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors, strict=True))
    ]
    await client.upsert(collection_name=collection, points=points)
    return len(chunks)


async def search_documents(
    user_id: str, query: str, api_key: str, top_k: int = 5
) -> list[str]:
    """在用户 Collection 中检索最相关的文档切片。"""
    client = await get_qdrant_client()
    collection = user_collection_name(user_id)
    embedder = get_embedder(api_key)
    query_vec = await embedder.aembed_query(query)
    results = await client.search(  # type: ignore[attr-defined]
        collection_name=collection, query_vector=query_vec, limit=top_k
    )
    return [r.payload["text"] for r in results if r.payload]
