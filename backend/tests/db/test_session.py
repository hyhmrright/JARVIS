# backend/tests/db/test_session.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.anyio
async def test_isolated_session_commits_on_success():
    """isolated_session() must commit the session when no exception is raised."""
    mock_session = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db.session.AsyncSessionLocal", return_value=mock_cm):
        from app.db.session import isolated_session

        async with isolated_session() as _:
            pass  # no exception

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_isolated_session_rolls_back_on_exception():
    """isolated_session() must roll back and re-raise when an exception occurs."""
    mock_session = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db.session.AsyncSessionLocal", return_value=mock_cm):
        from app.db.session import isolated_session

        with pytest.raises(ValueError, match="boom"):
            async with isolated_session() as _:
                raise ValueError("boom")

    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_awaited()
