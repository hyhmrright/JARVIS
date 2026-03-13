import asyncio
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings

_COLLECTIONS_JSON = (
    Path(__file__).resolve().parents[3] / "database" / "qdrant" / "collections.json"
)

_DEFAULT_VECTOR_CONFIG: dict[str, Any] = {"size": 1536, "distance": "Cosine"}

# Lazy-initialized on first use; avoids import-time network calls that
# break test collection and CLI scripts that import this module.
_client: AsyncQdrantClient | None = None
_client_lock = asyncio.Lock()

# Track which collections have been confirmed/created this process,
# guarded by a single lock to avoid unbounded dict growth.
_created_collections: set[str] = set()
_collection_lock = asyncio.Lock()


def user_collection_name(user_id: str) -> str:
    """返回用户的 Qdrant Collection 名称。"""
    return f"user_{user_id}"


@lru_cache
def _load_vector_config() -> dict[str, Any]:
    """从 database/qdrant/collections.json 读取向量配置。"""
    if _COLLECTIONS_JSON.exists():
        data = json.loads(_COLLECTIONS_JSON.read_text())
        return data["collections"][0]["vectors"]
    return _DEFAULT_VECTOR_CONFIG


async def get_qdrant_client() -> AsyncQdrantClient:
    """返回 Qdrant 异步客户端单例（首次调用时创建）。"""
    global _client
    if _client is not None:
        return _client
    async with _client_lock:
        if _client is None:
            _client = AsyncQdrantClient(url=settings.qdrant_url)
        return _client


async def close_qdrant_client() -> None:
    """关闭 Qdrant 客户端连接。"""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


async def ensure_collection(collection_name: str) -> None:
    """确保指定 Qdrant Collection 存在（幂等、并发安全）。"""
    if collection_name in _created_collections:
        return
    async with _collection_lock:
        if collection_name in _created_collections:
            return
        client = await get_qdrant_client()
        if await client.collection_exists(collection_name):
            _created_collections.add(collection_name)
            return
        vec_cfg = _load_vector_config()
        distance = getattr(Distance, vec_cfg["distance"].upper(), Distance.COSINE)
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vec_cfg["size"], distance=distance),
        )
        _created_collections.add(collection_name)


async def ensure_user_collection(user_id: str) -> None:
    """确保用户的 Qdrant Collection 存在（幂等、并发安全）。"""
    await ensure_collection(user_collection_name(user_id))
