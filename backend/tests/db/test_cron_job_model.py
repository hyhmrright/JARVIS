"""Tests for CronJob domain model methods."""

import uuid

import pytest

from app.db.models.scheduler import CronJob


def test_create_factory():
    job = CronJob.create(
        user_id=uuid.uuid4(),
        schedule="0 * * * *",
        task="check website",
        trigger_type="cron",
    )
    assert job.id is not None
    assert job.schedule == "0 * * * *"
    assert job.task == "check website"
    assert job.trigger_type == "cron"
    assert job.is_active is True


def test_create_factory_with_workspace():
    ws_id = uuid.uuid4()
    job = CronJob.create(
        user_id=uuid.uuid4(),
        schedule="*/5 * * * *",
        task="monitor",
        trigger_type="web_watcher",
        workspace_id=ws_id,
        trigger_metadata={"url": "https://example.com"},
    )
    assert job.workspace_id == ws_id
    assert job.trigger_metadata == {"url": "https://example.com"}


def test_validate_trigger_type_valid():
    CronJob.validate_trigger_type("cron")
    CronJob.validate_trigger_type("web_watcher")
    CronJob.validate_trigger_type("semantic_watcher")
    CronJob.validate_trigger_type("email")


def test_validate_trigger_type_invalid():
    with pytest.raises(ValueError, match="Invalid trigger_type"):
        CronJob.validate_trigger_type("invalid_type")


def test_toggle_active():
    job = CronJob.create(
        user_id=uuid.uuid4(),
        schedule="0 * * * *",
        task="test",
        trigger_type="cron",
    )
    assert job.is_active is True
    job.toggle()
    assert job.is_active is False
    job.toggle()
    assert job.is_active is True
