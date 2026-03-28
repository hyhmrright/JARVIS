"""API-layer conftest: fixtures only relevant to tests/api/.

Placing _suppress_chat_async_session here (instead of the root conftest)
keeps the Mystery Guest scope tight — the patch is only active when running
API tests, not across the entire suite.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
async def _suppress_chat_async_session():
    """Mock AsyncSessionLocal in chat routes to prevent cross-event-loop contamination.

    The streaming generator in chat/routes.py opens its own AsyncSessionLocal
    session (separate from the request-level session, which has already returned).
    Those connections bind to the calling event loop and are invalid in the next
    test's event loop, causing asyncpg "another operation is in progress".
    """
    patched_session = MagicMock()
    patched_session.__aenter__ = AsyncMock(return_value=patched_session)
    patched_session.__aexit__ = AsyncMock(return_value=None)
    patched_session.begin = MagicMock(return_value=patched_session)
    patched_session.scalar = AsyncMock(return_value=None)
    _scalars = MagicMock()
    _scalars.all = MagicMock(return_value=[])
    _execute_result = MagicMock()
    _execute_result.scalars = MagicMock(return_value=_scalars)
    patched_session.execute = AsyncMock(return_value=_execute_result)
    patched_session.add = MagicMock()
    patched_session.flush = AsyncMock()
    patched_session.get = AsyncMock(return_value=None)
    with patch("app.api.chat.routes.AsyncSessionLocal", return_value=patched_session):
        yield
