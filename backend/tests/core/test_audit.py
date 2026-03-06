"""Unit tests for the audit log utility."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.core.audit import log_action


@pytest.fixture
def mock_request():
    req = MagicMock()
    req.client.host = "1.2.3.4"
    req.headers = {"user-agent": "TestAgent/1.0"}
    return req


@pytest.fixture
def mock_session():
    """Async session mock with begin() context manager."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    mock_begin = AsyncMock()
    mock_begin.__aenter__ = AsyncMock(return_value=None)
    mock_begin.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=mock_begin)
    return session


@pytest.mark.asyncio
async def test_log_action_writes_to_db(mock_session, mock_request):
    """log_action should create an AuditLog row."""
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    with patch("app.core.audit.AsyncSessionLocal", return_value=mock_session):
        await log_action(
            "user.login",
            user_id=user_id,
            resource_type="user",
            resource_id=str(user_id),
            request=mock_request,
        )

    mock_session.add.assert_called_once()
    row = mock_session.add.call_args[0][0]
    assert row.action == "user.login"
    assert row.user_id == user_id
    assert row.ip_address == "1.2.3.4"
    assert row.user_agent == "TestAgent/1.0"


@pytest.mark.asyncio
async def test_log_action_without_request(mock_session):
    """log_action works when no request is provided."""
    with patch("app.core.audit.AsyncSessionLocal", return_value=mock_session):
        await log_action("system.startup")

    mock_session.add.assert_called_once()
    row = mock_session.add.call_args[0][0]
    assert row.action == "system.startup"
    assert row.ip_address is None
    assert row.user_id is None


@pytest.mark.asyncio
async def test_log_action_swallows_db_error():
    """log_action must not raise even if DB write fails."""
    with patch("app.core.audit.AsyncSessionLocal", side_effect=Exception("db down")):
        # Should not raise
        await log_action("user.login", user_id=None)


@pytest.mark.asyncio
async def test_log_action_uses_x_real_ip(mock_session):
    """X-Real-IP header takes priority over request.client.host."""
    req = MagicMock()
    req.client.host = "10.0.0.1"  # internal proxy IP
    req.headers = {"x-real-ip": "203.0.113.5", "user-agent": "TestAgent/1.0"}

    with patch("app.core.audit.AsyncSessionLocal", return_value=mock_session):
        await log_action("user.login", request=req)

    row = mock_session.add.call_args[0][0]
    assert row.ip_address == "203.0.113.5"


@pytest.mark.asyncio
async def test_log_action_uses_x_forwarded_for(mock_session):
    """X-Forwarded-For first IP used when X-Real-IP is absent."""
    req = MagicMock()
    req.client.host = "10.0.0.1"
    req.headers = {"x-forwarded-for": "198.51.100.1, 10.0.0.1", "user-agent": "Bot"}

    with patch("app.core.audit.AsyncSessionLocal", return_value=mock_session):
        await log_action("user.login", request=req)

    row = mock_session.add.call_args[0][0]
    assert row.ip_address == "198.51.100.1"


@pytest.mark.asyncio
async def test_log_action_no_client(mock_session):
    """request.client being None does not raise."""
    req = MagicMock()
    req.client = None
    req.headers = {"user-agent": "Bot"}

    with patch("app.core.audit.AsyncSessionLocal", return_value=mock_session):
        await log_action("user.login", request=req)

    row = mock_session.add.call_args[0][0]
    assert row.ip_address is None
