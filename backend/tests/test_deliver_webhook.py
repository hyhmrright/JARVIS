"""Unit tests for the deliver_webhook ARQ task."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _create_mock_db() -> AsyncMock:
    """Create a mock AsyncSession with context manager support."""
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=None)
    mock_db.get = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.begin = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    return mock_db


def _create_fake_webhook() -> MagicMock:
    """Create a fake webhook object for testing."""
    webhook = MagicMock()
    webhook.id = uuid.uuid4()
    webhook.is_active = True
    webhook.task_template = "Handle: {payload}"
    webhook.user_id = uuid.uuid4()
    return webhook


@pytest.mark.asyncio
async def test_deliver_webhook_success_even_if_reply_starts_with_apology():
    """deliver_webhook marks success for any non-exception reply, even if it starts
    with an apology word — the error contract is exception-based, not string-based."""
    webhook_id = str(uuid.uuid4())
    fake_webhook = _create_fake_webhook()
    fake_webhook.id = uuid.UUID(webhook_id)

    mock_db = _create_mock_db()
    mock_db.get = AsyncMock(return_value=fake_webhook)

    ctx = {"job_try": 1}

    with (
        patch("app.worker.AsyncSessionLocal", return_value=mock_db),
        patch(
            "app.worker.run_agent_for_user",
            # Agent legitimately returns content that starts with "抱歉" (an apology)
            AsyncMock(return_value="抱歉我之前的回答有误，正确答案是..."),
        ),
    ):
        from app.worker import deliver_webhook

        await deliver_webhook(ctx, webhook_id=webhook_id, payload={"key": "val"})

    stmt = mock_db.execute.call_args_list[-1][0][0]
    assert "success" in str(stmt.compile(compile_kwargs={"literal_binds": True}))


@pytest.mark.asyncio
async def test_deliver_webhook_success():
    """deliver_webhook marks delivery success when agent returns a non-error reply."""
    webhook_id = str(uuid.uuid4())
    fake_webhook = _create_fake_webhook()
    fake_webhook.id = uuid.UUID(webhook_id)

    mock_db = _create_mock_db()
    mock_db.get = AsyncMock(return_value=fake_webhook)

    ctx = {"job_try": 1}

    with (
        patch("app.worker.AsyncSessionLocal", return_value=mock_db),
        patch(
            "app.worker.run_agent_for_user",
            AsyncMock(return_value="Done successfully"),
        ),
    ):
        from app.worker import deliver_webhook

        await deliver_webhook(ctx, webhook_id=webhook_id, payload={"key": "val"})

    assert mock_db.execute.called
    # Verify the UPDATE was called with a status="success" value
    stmt = mock_db.execute.call_args_list[-1][0][0]
    assert "success" in str(stmt.compile(compile_kwargs={"literal_binds": True}))


@pytest.mark.asyncio
async def test_deliver_webhook_retries_on_failure():
    """deliver_webhook raises RuntimeError on failure when retries remain."""
    webhook_id = str(uuid.uuid4())
    fake_webhook = _create_fake_webhook()
    fake_webhook.id = uuid.UUID(webhook_id)

    mock_db = _create_mock_db()
    mock_db.get = AsyncMock(return_value=fake_webhook)

    ctx = {"job_try": 1}

    with (
        patch("app.worker.AsyncSessionLocal", return_value=mock_db),
        patch(
            "app.worker.run_agent_for_user",
            AsyncMock(side_effect=RuntimeError("agent crashed")),
        ),
    ):
        from app.worker import deliver_webhook

        with pytest.raises(RuntimeError, match="will retry"):
            await deliver_webhook(ctx, webhook_id=webhook_id, payload={})


@pytest.mark.asyncio
async def test_deliver_webhook_no_retry_on_last_attempt():
    """deliver_webhook does NOT raise on the final attempt — just marks failed."""
    webhook_id = str(uuid.uuid4())
    fake_webhook = _create_fake_webhook()
    fake_webhook.id = uuid.UUID(webhook_id)

    mock_db = _create_mock_db()
    mock_db.get = AsyncMock(return_value=fake_webhook)

    # attempt=3 is the final attempt (max_tries=3 in WorkerSettings)
    ctx = {"job_try": 3}

    with (
        patch("app.worker.AsyncSessionLocal", return_value=mock_db),
        patch(
            "app.worker.run_agent_for_user",
            AsyncMock(side_effect=RuntimeError("agent crashed")),
        ),
    ):
        from app.worker import deliver_webhook

        # Should NOT raise on final attempt (attempt 3 >= len([1,10]))
        await deliver_webhook(ctx, webhook_id=webhook_id, payload={})
