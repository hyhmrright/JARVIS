"""Tests for CronService business logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.cron_service import CronService


def _make_db() -> AsyncMock:
    """Return a minimal mock AsyncSession."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db


def _make_job(
    *,
    is_active: bool = True,
    trigger_type: str = "cron",
    schedule: str = "0 * * * *",
) -> MagicMock:
    job = MagicMock()
    job.id = uuid.uuid4()
    job.schedule = schedule
    job.trigger_type = trigger_type
    job.is_active = is_active
    job.next_run_at = None
    job.trigger_metadata = None

    def _toggle() -> None:
        job.is_active = not job.is_active

    job.toggle = _toggle
    return job


# ---------------------------------------------------------------------------
# check_quota
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_check_quota_under_limit_passes() -> None:
    db = _make_db()
    db.scalar = AsyncMock(return_value=2)

    with patch("app.services.cron_service.settings") as mock_settings:
        mock_settings.max_cron_jobs_per_user = 5
        svc = CronService(db)
        # Should not raise
        await svc.check_quota(uuid.uuid4())


@pytest.mark.anyio
async def test_check_quota_at_limit_raises_429() -> None:
    db = _make_db()
    db.scalar = AsyncMock(return_value=5)

    with patch("app.services.cron_service.settings") as mock_settings:
        mock_settings.max_cron_jobs_per_user = 5
        svc = CronService(db)
        with pytest.raises(HTTPException) as exc_info:
            await svc.check_quota(uuid.uuid4())
        assert exc_info.value.status_code == 429
        assert "quota exceeded" in exc_info.value.detail


@pytest.mark.anyio
async def test_check_quota_none_count_treated_as_zero() -> None:
    db = _make_db()
    db.scalar = AsyncMock(return_value=None)

    with patch("app.services.cron_service.settings") as mock_settings:
        mock_settings.max_cron_jobs_per_user = 5
        svc = CronService(db)
        await svc.check_quota(uuid.uuid4())  # should not raise


# ---------------------------------------------------------------------------
# prepare_trigger_metadata
# ---------------------------------------------------------------------------


def test_prepare_trigger_metadata_none_returns_none() -> None:
    svc = CronService(MagicMock())
    assert svc.prepare_trigger_metadata("cron", None) is None


def test_prepare_trigger_metadata_non_email_unchanged() -> None:
    svc = CronService(MagicMock())
    meta = {"url": "https://example.com", "selector": "h1"}
    result = svc.prepare_trigger_metadata("web_watcher", meta)
    assert result == meta
    assert result is not meta  # must be a copy


def test_prepare_trigger_metadata_email_encrypts_password() -> None:
    svc = CronService(MagicMock())
    meta = {"imap_host": "imap.example.com", "imap_password": "secret"}

    with patch(
        "app.services.cron_service.fernet_encrypt", return_value="ENCRYPTED"
    ) as mock_enc:
        result = svc.prepare_trigger_metadata("email", meta)

    mock_enc.assert_called_once_with("secret")
    assert result is not None
    assert result["imap_password"] == "ENCRYPTED"
    assert result["imap_host"] == "imap.example.com"
    # Original dict must not be mutated
    assert meta["imap_password"] == "secret"


def test_prepare_trigger_metadata_email_without_password_unchanged() -> None:
    svc = CronService(MagicMock())
    meta = {"imap_host": "imap.example.com"}
    result = svc.prepare_trigger_metadata("email", meta)
    assert result == meta


# ---------------------------------------------------------------------------
# create_job
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_job_invalid_trigger_type_raises_400() -> None:
    db = _make_db()
    svc = CronService(db)
    with pytest.raises(HTTPException) as exc_info:
        await svc.create_job(
            user_id=uuid.uuid4(),
            schedule="0 * * * *",
            task="check",
            trigger_type="bad_type",
        )
    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_create_job_invalid_metadata_raises_422() -> None:
    db = _make_db()

    def _bad_validate(trigger_type: str, metadata: dict) -> None:
        raise ValueError("missing required field")

    with patch(
        "app.services.cron_service.validate_trigger_metadata",
        side_effect=_bad_validate,
    ):
        svc = CronService(db)
        svc.check_quota = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await svc.create_job(
                user_id=uuid.uuid4(),
                schedule="0 * * * *",
                task="check",
                trigger_type="cron",
            )
    assert exc_info.value.status_code == 422


@pytest.mark.anyio
async def test_create_job_calls_quota_and_persists() -> None:
    db = _make_db()

    fake_job = _make_job()
    fake_job.is_active = True

    next_run = datetime(2030, 1, 1, tzinfo=UTC)

    with (
        patch("app.services.cron_service.validate_trigger_metadata"),
        patch("app.services.cron_service.CronJob.validate_trigger_type"),
        patch("app.services.cron_service.CronJob.create", return_value=fake_job),
        patch(
            "app.services.cron_service.register_cron_job", return_value=next_run
        ) as mock_reg,
    ):
        svc = CronService(db)
        svc.check_quota = AsyncMock()
        result = await svc.create_job(
            user_id=uuid.uuid4(),
            schedule="0 * * * *",
            task="check",
            trigger_type="cron",
        )

    db.add.assert_called_once_with(fake_job)
    db.commit.assert_called()
    mock_reg.assert_called_once()
    assert result.next_run_at == next_run


@pytest.mark.anyio
async def test_create_job_inactive_job_skips_registration() -> None:
    db = _make_db()

    fake_job = _make_job(is_active=False)

    with (
        patch("app.services.cron_service.validate_trigger_metadata"),
        patch("app.services.cron_service.CronJob.validate_trigger_type"),
        patch("app.services.cron_service.CronJob.create", return_value=fake_job),
        patch("app.services.cron_service.register_cron_job") as mock_reg,
    ):
        svc = CronService(db)
        svc.check_quota = AsyncMock()
        await svc.create_job(
            user_id=uuid.uuid4(),
            schedule="0 * * * *",
            task="check",
            trigger_type="cron",
        )

    mock_reg.assert_not_called()


# ---------------------------------------------------------------------------
# update_job
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_update_job_schedule_while_active() -> None:
    db = _make_db()
    job = _make_job(is_active=True)
    next_run = datetime(2030, 6, 1, tzinfo=UTC)

    with (
        patch("app.services.cron_service.unregister_cron_job") as mock_unreg,
        patch(
            "app.services.cron_service.register_cron_job", return_value=next_run
        ) as mock_reg,
    ):
        svc = CronService(db)
        result = await svc.update_job(job, schedule="*/5 * * * *")

    assert result.schedule == "*/5 * * * *"
    mock_unreg.assert_called_once_with(str(job.id))
    mock_reg.assert_called_once()
    assert result.next_run_at == next_run
    db.commit.assert_called()


@pytest.mark.anyio
async def test_update_job_invalid_metadata_raises_422() -> None:
    db = _make_db()
    job = _make_job()

    with patch(
        "app.services.cron_service.validate_trigger_metadata",
        side_effect=ValueError("bad field"),
    ):
        svc = CronService(db)
        with pytest.raises(HTTPException) as exc_info:
            await svc.update_job(job, trigger_metadata={"bad": "data"})
    assert exc_info.value.status_code == 422


@pytest.mark.anyio
async def test_update_job_task_only_inactive_no_registration() -> None:
    db = _make_db()
    job = _make_job(is_active=False)

    with patch("app.services.cron_service.register_cron_job") as mock_reg:
        svc = CronService(db)
        result = await svc.update_job(job, task="new task")

    assert result.task == "new task"
    mock_reg.assert_not_called()
    db.commit.assert_called()


# ---------------------------------------------------------------------------
# toggle_job
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_toggle_job_activates_and_registers() -> None:
    db = _make_db()
    job = _make_job(is_active=False)
    next_run = datetime(2030, 6, 1, tzinfo=UTC)

    with patch(
        "app.services.cron_service.register_cron_job", return_value=next_run
    ) as mock_reg:
        svc = CronService(db)
        result = await svc.toggle_job(job)

    assert result.is_active is True
    mock_reg.assert_called_once()
    assert result.next_run_at == next_run


@pytest.mark.anyio
async def test_toggle_job_deactivates_and_unregisters() -> None:
    db = _make_db()
    job = _make_job(is_active=True)

    with (
        patch("app.services.cron_service.unregister_cron_job") as mock_unreg,
        patch("app.services.cron_service.register_cron_job") as mock_reg,
    ):
        svc = CronService(db)
        result = await svc.toggle_job(job)

    assert result.is_active is False
    mock_unreg.assert_called_once_with(str(job.id))
    mock_reg.assert_not_called()
    assert result.next_run_at is None


# ---------------------------------------------------------------------------
# delete_job
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_delete_job_unregisters_and_deletes() -> None:
    db = _make_db()
    job = _make_job()

    with patch("app.services.cron_service.unregister_cron_job") as mock_unreg:
        svc = CronService(db)
        await svc.delete_job(job)

    mock_unreg.assert_called_once_with(str(job.id))
    db.delete.assert_called_once_with(job)
    db.commit.assert_called()
