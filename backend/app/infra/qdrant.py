import json
from functools import lru_cache
from pathlib import Path

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings

_COLLECTIONS_JSON = (
    Path(__file__).resolve().parents[3] / "database" / "qdrant" / "collections.json"
)


@lru_cache
def _load_vector_config() -> dict:
    """从 database/qdrant/collections.json 读取向量配置。"""
    if _COLLECTIONS_JSON.exists():
        data = json.loads(_COLLECTIONS_JSON.read_text())
        return data["collections"][0]["vectors"]
    return {"size": 1536, "distance": "Cosine"}


def get_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=settings.qdrant_url)


async def ensure_user_collection(user_id: str) -> None:
    """确保用户的 Qdrant Collection 存在（幂等）。"""
    client = get_qdrant_client()
    collection_name = f"user_{user_id}"
    exists = await client.collection_exists(collection_name)
    if not exists:
        vec_cfg = _load_vector_config()
        distance = getattr(Distance, vec_cfg["distance"].upper(), Distance.COSINE)
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vec_cfg["size"], distance=distance),
        )
