import uuid

from qdrant_client.models import PointStruct

from app.infra.qdrant import ensure_user_collection, get_qdrant_client
from app.rag.chunker import chunk_text
from app.rag.embedder import get_embedder


async def index_document(user_id: str, doc_id: str, text: str, api_key: str) -> int:
    await ensure_user_collection(user_id)
    client = get_qdrant_client()
    collection = f"user_{user_id}"

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
    client = get_qdrant_client()
    collection = f"user_{user_id}"
    embedder = get_embedder(api_key)
    query_vec = await embedder.aembed_query(query)
    results = await client.search(
        collection_name=collection, query_vector=query_vec, limit=top_k
    )
    return [r.payload["text"] for r in results if r.payload]
