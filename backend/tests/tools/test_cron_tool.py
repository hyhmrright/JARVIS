"""Tests for cron scheduling tools."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.tools.cron_tool import create_cron_tools


async def test_cron_set_creates_job() -> None:
    """cron_set should persist a job and return a confirmation string."""
    mock_job = MagicMock()
    mock_job.id = uuid.UUID("00000000-0000-0000-0000-000000000099")

    mock_db = AsyncMock()
    mock_db.add = MagicMock()  # Session.add() is synchronous in SQLAlchemy
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda j: setattr(j, "id", mock_job.id))

    with patch("app.tools.cron_tool.AsyncSessionLocal") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        cron_set, _, _ = create_cron_tools("00000000-0000-0000-0000-000000000001")
        result = await cron_set.ainvoke(
            {
                "schedule": "0 9 * * 1-5",
                "task": "Send daily report",
            }
        )

    assert "Send daily report" in result
    assert "0 9 * * 1-5" in result


async def test_cron_list_no_jobs() -> None:
    """cron_list returns a friendly message when no jobs exist."""
    mock_db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_db.scalars = AsyncMock(return_value=mock_scalars)

    with patch("app.tools.cron_tool.AsyncSessionLocal") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        _, cron_list, _ = create_cron_tools("00000000-0000-0000-0000-000000000001")
        result = await cron_list.ainvoke({})

    assert "No active cron jobs" in result


async def test_cron_list_with_jobs() -> None:
    """cron_list returns job details including schedule and last run time."""
    from app.db.models import CronJob

    fake_job = MagicMock(spec=CronJob)
    fake_job.id = uuid.UUID("00000000-0000-0000-0000-000000000042")
    fake_job.task = "Daily report"
    fake_job.schedule = "0 9 * * 1-5"
    fake_job.last_run_at = None

    mock_db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [fake_job]
    mock_db.scalars = AsyncMock(return_value=mock_scalars)

    with patch("app.tools.cron_tool.AsyncSessionLocal") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        _, cron_list, _ = create_cron_tools("00000000-0000-0000-0000-000000000001")
        result = await cron_list.ainvoke({})

    assert "Daily report" in result
    assert "0 9 * * 1-5" in result
    assert "never" in result


async def test_cron_set_invalid_expression() -> None:
    """cron_set returns an error for an invalid cron expression without touching DB."""
    cron_set, _, _ = create_cron_tools("00000000-0000-0000-0000-000000000001")
    result = await cron_set.ainvoke({"schedule": "not a cron", "task": "anything"})
    assert "Invalid cron expression" in result


async def test_cron_delete_invalid_uuid() -> None:
    """cron_delete returns error message for invalid UUID without DB access."""
    _, _, cron_delete = create_cron_tools("00000000-0000-0000-0000-000000000001")
    result = await cron_delete.ainvoke({"job_id": "not-a-uuid"})
    assert "Invalid job ID" in result


async def test_cron_delete_not_found() -> None:
    """cron_delete returns not found message when job doesn't exist."""
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    with patch("app.tools.cron_tool.AsyncSessionLocal") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        _, _, cron_delete = create_cron_tools("00000000-0000-0000-0000-000000000001")
        result = await cron_delete.ainvoke(
            {"job_id": "00000000-0000-0000-0000-000000000099"}
        )

    assert "not found" in result


async def test_cron_delete_wrong_user() -> None:
    """cron_delete does not allow deleting another user's job."""
    from app.db.models import CronJob

    other_user_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    fake_job = MagicMock(spec=CronJob)
    fake_job.user_id = other_user_id

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=fake_job)

    with patch("app.tools.cron_tool.AsyncSessionLocal") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        _, _, cron_delete = create_cron_tools("00000000-0000-0000-0000-000000000001")
        result = await cron_delete.ainvoke(
            {"job_id": "00000000-0000-0000-0000-000000000099"}
        )

    assert "not found" in result
