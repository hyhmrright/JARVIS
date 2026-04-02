"""Scheduler domain models: CronJob, JobExecution, Webhook, WebhookDelivery,
WebhookDeadLetter."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CronJob(Base):
    __tablename__ = "cron_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schedule: Mapped[str] = mapped_column(String(100), nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="cron"
    )
    trigger_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    executions: Mapped[list["JobExecution"]] = relationship(
        "JobExecution", back_populates="job", cascade="all, delete-orphan"
    )

    _VALID_TRIGGER_TYPES = frozenset(
        {"cron", "web_watcher", "semantic_watcher", "email"}
    )

    @classmethod
    def create(
        cls,
        *,
        user_id: uuid.UUID,
        schedule: str,
        task: str,
        trigger_type: str,
        workspace_id: uuid.UUID | None = None,
        trigger_metadata: dict | None = None,
        is_active: bool = True,
    ) -> "CronJob":
        """Factory method — validates trigger_type before construction."""
        cls.validate_trigger_type(trigger_type)
        return cls(
            id=uuid.uuid4(),
            user_id=user_id,
            schedule=schedule,
            task=task,
            trigger_type=trigger_type,
            workspace_id=workspace_id,
            trigger_metadata=trigger_metadata,
            is_active=is_active,
        )

    @classmethod
    def validate_trigger_type(cls, trigger_type: str) -> None:
        """Raise ValueError if trigger_type is not recognized."""
        if trigger_type not in cls._VALID_TRIGGER_TYPES:
            valid = sorted(cls._VALID_TRIGGER_TYPES)
            raise ValueError(
                f"Invalid trigger_type '{trigger_type}'. Must be one of: {valid}"
            )

    def toggle(self) -> None:
        """Flip the is_active flag."""
        self.is_active = not self.is_active


class JobExecution(Base):
    __tablename__ = "job_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cron_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # fired | skipped | error
    trigger_ctx: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    agent_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")

    job: Mapped["CronJob"] = relationship("CronJob", back_populates="executions")


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    task_template: Mapped[str] = mapped_column(Text, nullable=False)
    secret_token: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trigger_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    user: Mapped["User"] = relationship("User")
    deliveries: Mapped[list["WebhookDelivery"]] = relationship(
        "WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan"
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'success', 'failed')",
            name="ck_webhook_deliveries_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1", default=1
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    webhook: Mapped["Webhook"] = relationship("Webhook", back_populates="deliveries")


class WebhookDeadLetter(Base):
    __tablename__ = "webhook_dead_letters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
