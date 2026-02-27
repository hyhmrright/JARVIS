import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import app.infra.qdrant as qdrant_mod
from app.infra.qdrant import ensure_user_collection, user_collection_name


def test_collections_json_is_valid():
    """database/qdrant/collections.json 应可被解析。"""
    path = (
        Path(__file__).resolve().parents[3] / "database" / "qdrant" / "collections.json"
    )
    data = json.loads(path.read_text())
    assert "collections" in data
    coll = data["collections"][0]
    assert coll["vectors"]["size"] == 1536
    assert coll["vectors"]["distance"] == "Cosine"


def test_user_collection_name():
    """user_collection_name 应返回正确格式。"""
    assert user_collection_name("abc-123") == "user_abc-123"


@pytest.mark.anyio
async def test_ensure_user_collection_creates_when_missing():
    """当 collection 不存在时应创建。"""
    qdrant_mod._created_collections.discard("user_test-user-id")

    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = False

    with patch(
        "app.infra.qdrant.get_qdrant_client",
        side_effect=AsyncMock(return_value=mock_client),
    ):
        await ensure_user_collection("test-user-id")

    mock_client.create_collection.assert_called_once()


@pytest.mark.anyio
async def test_ensure_user_collection_skips_when_exists():
    """当 collection 已存在时不应重复创建。"""
    qdrant_mod._created_collections.discard("user_test-user-id")

    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True

    with patch(
        "app.infra.qdrant.get_qdrant_client",
        side_effect=AsyncMock(return_value=mock_client),
    ):
        await ensure_user_collection("test-user-id")

    mock_client.create_collection.assert_not_called()
