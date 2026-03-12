# backend/tests/test_job_execution_model.py
"""Smoke test: verify JobExecution model imports and has expected columns."""

from app.db.models import CronJob, JobExecution


def test_job_execution_columns():
    cols = {c.key for c in JobExecution.__table__.columns}
    assert "id" in cols
    assert "job_id" in cols
    assert "fired_at" in cols
    assert "status" in cols
    assert "trigger_ctx" in cols
    assert "agent_result" in cols
    assert "duration_ms" in cols
    assert "error_msg" in cols
    assert "attempt" in cols
    assert "run_group_id" in cols


def test_cron_job_has_executions_relationship():
    assert hasattr(CronJob, "executions")
