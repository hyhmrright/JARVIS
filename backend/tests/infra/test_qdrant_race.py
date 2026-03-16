"""Regression test: concurrent ensure_collection must not raise on already-exists."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qdrant_client.http.exceptions import UnexpectedResponse


def _make_already_exists_error() -> UnexpectedResponse:
    """Simulate Qdrant's response when a collection already exists."""
    return UnexpectedResponse(
        status_code=400,
        reason_phrase="Bad Request",
        content=b'{"status":{"error":"Collection already exists!"}}',
        headers={},
    )


@pytest.mark.anyio
async def test_concurrent_ensure_collection_no_exception():
    """10 concurrent coroutines calling ensure_collection for the same name
    must not raise, even if Qdrant returns 'already exists' on create_collection.

    Scenario:
    - collection_exists() returns False on first pre-create check (race window),
      then True on the post-create fallback check.
    - create_collection() raises 'already exists' (another process won the race).
    - After fix: the exception is caught, collection_exists() returns True,
      so we treat it as success and add the name to the cache.
    - Coroutines 2-10: name is already in _created_collections → immediate return.
    """
    collection_name = f"test_{uuid.uuid4().hex[:8]}"

    mock_client = MagicMock()
    # False = pre-create check (race window); True = post-create fallback check.
    mock_client.collection_exists = AsyncMock(side_effect=[False, True])
    mock_client.create_collection = AsyncMock(side_effect=_make_already_exists_error())

    import app.infra.qdrant as qdrant_mod

    original_created = qdrant_mod._created_collections.copy()
    qdrant_mod._created_collections.clear()
    try:
        with patch(
            "app.infra.qdrant.get_qdrant_client",
            AsyncMock(return_value=mock_client),
        ):
            tasks = [qdrant_mod.ensure_collection(collection_name) for _ in range(10)]
            # Must not raise any exception
            await asyncio.gather(*tasks)
        assert collection_name in qdrant_mod._created_collections
    finally:
        qdrant_mod._created_collections.clear()
        qdrant_mod._created_collections.update(original_created)
