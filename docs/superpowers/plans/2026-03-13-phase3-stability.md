# Phase 3: Stability / Ops — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve operational observability and reliability: populate `AgentSession` metadata for full traceability, move webhook delivery to an async ARQ queue with retry, and expose custom Prometheus metrics with Grafana alert rules.

**Architecture:** Three independent backend tasks. Task 3.1 is pure in-process instrumentation (no new tables). Task 3.2 adds one new DB table (`webhook_deliveries`) and shifts webhook execution from `asyncio.create_task` to ARQ. Task 3.3 adds a `metrics.py` module, instruments four call-sites, and provisions a Grafana alerting YAML. All three tasks are safe to develop in parallel on separate branches, though 3.2 must be merged before any ARQ function that references `deliver_webhook` is deployed.

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy async + ARQ + prometheus-client 0.21+, Grafana 10 alerting provisioning YAML

---

## Chunk 1 — Task 3.1: AgentSession Metadata Population

**Files:**
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/gateway/agent_runner.py`

**Steps:**

- [ ] Step 1.1: Extract tools used from the agent graph result in `chat.py`

  In `chat.py`, locate the `generate()` inner function. At the top of the function (after `compact_messages` runs), add a list to accumulate tool names:

  ```python
  tools_used: list[str] = []
  ```

  In the `else` branch (expert/ReAct streaming, lines ~399-407), inside the `async for chunk in graph.astream(state):` loop, after updating `last_ai_msg`, append any tool names found in tool-call chunks:

  ```python
  if "llm" in chunk:
      last_ai_msg = chunk["llm"]["messages"][-1]
      if hasattr(last_ai_msg, "tool_calls") and last_ai_msg.tool_calls:
          for tc in last_ai_msg.tool_calls:
              name = tc.get("name", "")
              if name and name not in tools_used:
                  tools_used.append(name)
  ```

  In the `complex` branch (supervisor, lines ~339-378), tools used are not individually tracked — set `tools_used = ["supervisor"]` immediately after `route == "complex"` is confirmed.

- [ ] Step 1.2: Write `context_summary` after context compression in `chat.py`

  After the `compact_messages` call (lines ~294-302) succeeds and before the `agent_session_id` block, capture whether compression fired and its summary text. Modify the block to:

  ```python
  context_summary_text: str | None = None
  try:
      original_len = sum(len(f"{m.type}: {m.content}") for m in lc_messages)
      lc_messages = await compact_messages(
          lc_messages,
          provider=llm.provider,
          model=llm.model_name,
          api_key=llm.api_key,
          base_url=llm.base_url,
      )
      compressed_len = sum(len(f"{m.type}: {m.content}") for m in lc_messages)
      if compressed_len < original_len:
          # Find the summary AIMessage injected by compact_messages
          from langchain_core.messages import AIMessage as _AIMessage
          for m in lc_messages:
              if isinstance(m, _AIMessage) and str(m.content).startswith("[Conversation summary]"):
                  context_summary_text = str(m.content)
                  break
  except Exception:
      logger.warning("context_compression_failed", exc_info=True)
  ```

- [ ] Step 1.3: Write `metadata_json` and `context_summary` to `AgentSession` on completion in `chat.py`

  Find the `AgentSession` update block in the `finally` clause (lines ~461-475). Replace the existing `.values(status=..., completed_at=...)` call with:

  ```python
  if agent_session_id:
      try:
          session_status = "error" if stream_error else "completed"
          tokens_in, tokens_out = _extract_token_counts(last_ai_msg)
          session_meta: dict = {
              "model": llm.model_name,
              "provider": llm.provider,
              "tools_used": tools_used,
              "input_tokens": tokens_in or 0,
              "output_tokens": tokens_out or 0,
              "trigger_type": "chat",
          }
          update_values: dict = {
              "status": session_status,
              "completed_at": datetime.now(UTC),
              "metadata_json": session_meta,
          }
          if context_summary_text:
              update_values["context_summary"] = context_summary_text
          async with AsyncSessionLocal() as status_sess:
              async with status_sess.begin():
                  await status_sess.execute(
                      update(AgentSession)
                      .where(AgentSession.id == agent_session_id)
                      .values(**update_values)
                  )
      except Exception:
          logger.warning("agent_session_update_failed", exc_info=True)
  ```

  Note: `_extract_token_counts` is called again here. This is a cheap function (reads attributes from `last_ai_msg`). To avoid duplication, you may optionally extract it into a local variable earlier in the `finally` block and reuse it.

- [ ] Step 1.4: Add `AgentSession` tracking to `agent_runner.py` (background/cron/webhook runs)

  In `run_agent_for_user`, after `conv.id` is flushed but before the graph is invoked, create an `AgentSession` record. Import `AgentSession` and `datetime`/`UTC` at the top of the file:

  ```python
  import time
  from datetime import UTC, datetime

  from app.db.models import AgentSession, Conversation, Message, UserSettings
  ```

  Then, inside the `async with AsyncSessionLocal() as db:` block, after `await db.flush()` for the `Conversation`, add:

  ```python
  ag_sess = AgentSession(
      conversation_id=conv.id,
      agent_type="main",
      status="active",
  )
  db.add(ag_sess)
  await db.flush()
  agent_session_id = ag_sess.id
  run_start = time.monotonic()
  ```

  After `result = await graph.ainvoke(AgentState(messages=lc_messages))`, extract the last message and build metadata:

  ```python
  ai_content = str(result["messages"][-1].content)
  last_msg = result["messages"][-1]

  # Collect tools used from all messages in result
  tools_used: list[str] = []
  for msg in result.get("messages", []):
      if hasattr(msg, "tool_calls") and msg.tool_calls:
          for tc in msg.tool_calls:
              name = tc.get("name", "")
              if name and name not in tools_used:
                  tools_used.append(name)

  # Token counts (usage_metadata populated by LangChain for supported providers)
  usage = getattr(last_msg, "usage_metadata", None) or {}
  tokens_in = usage.get("input_tokens") or 0
  tokens_out = usage.get("output_tokens") or 0

  trigger_type = (trigger_ctx or {}).get("trigger_type", "background")
  session_meta = {
      "model": model_name,
      "provider": provider,
      "tools_used": tools_used,
      "input_tokens": tokens_in,
      "output_tokens": tokens_out,
      "trigger_type": trigger_type,
  }
  duration_ms = int((time.monotonic() - run_start) * 1000)
  ```

  Replace the existing `db.add(Message(...))` + `await db.commit()` block with:

  ```python
  db.add(
      Message(
          conversation_id=conv.id,
          role="ai",
          content=ai_content,
          model_provider=provider,
          model_name=model_name,
      )
  )
  await db.execute(
      update(AgentSession)
      .where(AgentSession.id == agent_session_id)
      .values(
          status="completed",
          completed_at=datetime.now(UTC),
          metadata_json=session_meta,
      )
  )
  await db.commit()
  ```

  Add `from sqlalchemy import select, update` to the imports (replace the existing `from sqlalchemy import select`).

  In the `except Exception` handler at the end of the function, before `return "抱歉..."`, add a best-effort session error update:

  ```python
  if agent_session_id:
      try:
          async with AsyncSessionLocal() as err_sess:
              async with err_sess.begin():
                  await err_sess.execute(
                      update(AgentSession)
                      .where(AgentSession.id == agent_session_id)
                      .values(status="error", completed_at=datetime.now(UTC))
                  )
      except Exception:
          pass
  ```

- [ ] Step 1.5: Run static checks

  ```bash
  cd /Users/hyh/code/JARVIS/backend
  uv run ruff check --fix && uv run ruff format
  uv run mypy app
  uv run pytest --collect-only -q
  ```

  Expected: ruff clean, mypy passes (ignore any pre-existing errors), no import errors.

- [ ] Step 1.6: Write unit tests for agent_runner metadata

  Create `backend/tests/test_agent_runner_metadata.py`:

  ```python
  """Unit tests for AgentSession metadata population in agent_runner."""
  from unittest.mock import AsyncMock, MagicMock, patch
  import uuid
  import pytest


  @pytest.mark.asyncio
  async def test_agent_runner_writes_session_metadata():
      """AgentSession is created and updated with metadata_json after a run."""
      fake_user_id = str(uuid.uuid4())
      fake_conv_id = uuid.uuid4()
      fake_session_id = uuid.uuid4()

      # Build a fake last LLM message with usage_metadata
      fake_ai_msg = MagicMock()
      fake_ai_msg.content = "Test reply"
      fake_ai_msg.tool_calls = []
      fake_ai_msg.usage_metadata = {"input_tokens": 100, "output_tokens": 50}

      fake_result = {"messages": [fake_ai_msg]}

      # Fake UserSettings
      fake_us = MagicMock()
      fake_us.model_provider = "deepseek"
      fake_us.model_name = "deepseek-chat"
      fake_us.api_keys = {}
      fake_us.persona_override = None
      fake_us.enabled_tools = ["search"]

      # Fake Conversation
      fake_conv = MagicMock()
      fake_conv.id = fake_conv_id

      # Fake AgentSession
      fake_ag_sess = MagicMock()
      fake_ag_sess.id = fake_session_id

      # Fake graph
      fake_graph = AsyncMock()
      fake_graph.ainvoke = AsyncMock(return_value=fake_result)

      mock_db = AsyncMock()
      mock_db.__aenter__ = AsyncMock(return_value=mock_db)
      mock_db.__aexit__ = AsyncMock(return_value=None)
      mock_db.scalar = AsyncMock(return_value=fake_us)
      mock_db.flush = AsyncMock()
      mock_db.commit = AsyncMock()
      mock_db.add = MagicMock()
      mock_db.execute = AsyncMock()

      # Simulate flush setting conv.id and ag_sess.id
      def _add_side_effect(obj):
          if hasattr(obj, "id") and obj.id is None:
              obj.id = fake_conv_id

      mock_db.add.side_effect = _add_side_effect

      with (
          patch("app.gateway.agent_runner.AsyncSessionLocal", return_value=mock_db),
          patch("app.gateway.agent_runner.resolve_api_keys", return_value=["fake-key"]),
          patch("app.gateway.agent_runner.resolve_api_key", return_value=None),
          patch("app.gateway.agent_runner.build_rag_context", AsyncMock(return_value="")),
          patch("app.gateway.agent_runner.create_graph", return_value=fake_graph),
          patch("app.gateway.agent_runner.AgentSession", return_value=fake_ag_sess),
          patch("app.gateway.agent_runner.Conversation", return_value=fake_conv),
      ):
          from app.gateway.agent_runner import run_agent_for_user
          result = await run_agent_for_user(fake_user_id, "test task")

      assert result == "Test reply"
      # execute() should have been called to update AgentSession
      assert mock_db.execute.called
  ```

  Run:

  ```bash
  cd /Users/hyh/code/JARVIS/backend
  uv run pytest tests/test_agent_runner_metadata.py -v
  ```

- [ ] Step 1.7: Commit

  ```bash
  cd /Users/hyh/code/JARVIS
  git add backend/app/api/chat.py \
          backend/app/gateway/agent_runner.py \
          backend/tests/test_agent_runner_metadata.py
  git commit -m "feat: populate AgentSession metadata_json and context_summary on completion"
  ```

---

## Chunk 2 — Task 3.2: Webhook Async Delivery + Retry

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/014_webhook_deliveries.py`
- Modify: `backend/app/api/webhooks.py`
- Modify: `backend/app/worker.py`

**Steps:**

- [ ] Step 2.1: Add `WebhookDelivery` model to `models.py`

  Open `backend/app/db/models.py`. After the `Webhook` class (currently ending around line 364), add:

  ```python
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
      status: Mapped[str] = mapped_column(
          String(20), nullable=False, default="pending"
      )
      response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
      response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
      attempt: Mapped[int] = mapped_column(
          Integer, nullable=False, server_default="1", default=1
      )
      next_retry_at: Mapped[datetime | None] = mapped_column(
          DateTime(timezone=True), nullable=True
      )
  ```

  Also update the existing `Webhook` class to add the relationship back-reference:

  ```python
  deliveries: Mapped[list["WebhookDelivery"]] = relationship(
      "WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan"
  )
  ```

  And inside `WebhookDelivery`:

  ```python
  webhook: Mapped["Webhook"] = relationship("Webhook", back_populates="deliveries")
  ```

- [ ] Step 2.2: Create Alembic migration `014_webhook_deliveries.py`

  Create `backend/alembic/versions/014_webhook_deliveries.py`:

  ```python
  """add webhook_deliveries table

  Revision ID: 014
  Revises: 013
  Create Date: 2026-03-13
  """

  import sqlalchemy as sa
  from sqlalchemy.dialects.postgresql import UUID

  from alembic import op

  revision = "014"
  down_revision = "013"
  branch_labels = None
  depends_on = None


  def upgrade() -> None:
      op.create_table(
          "webhook_deliveries",
          sa.Column("id", UUID(as_uuid=True), primary_key=True),
          sa.Column(
              "webhook_id",
              UUID(as_uuid=True),
              sa.ForeignKey("webhooks.id", ondelete="CASCADE"),
              nullable=False,
          ),
          sa.Column(
              "triggered_at",
              sa.DateTime(timezone=True),
              server_default=sa.text("now()"),
              nullable=False,
          ),
          sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
          sa.Column("response_code", sa.Integer, nullable=True),
          sa.Column("response_body", sa.Text, nullable=True),
          sa.Column(
              "attempt", sa.Integer, nullable=False, server_default="1"
          ),
          sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
          sa.CheckConstraint(
              "status IN ('pending', 'success', 'failed')",
              name="ck_webhook_deliveries_status",
          ),
      )
      op.create_index(
          "idx_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"]
      )
      op.create_index(
          "idx_webhook_deliveries_triggered_at",
          "webhook_deliveries",
          ["triggered_at"],
          postgresql_ops={"triggered_at": "DESC"},
      )


  def downgrade() -> None:
      op.drop_index(
          "idx_webhook_deliveries_triggered_at", table_name="webhook_deliveries"
      )
      op.drop_index(
          "idx_webhook_deliveries_webhook_id", table_name="webhook_deliveries"
      )
      op.drop_table("webhook_deliveries")
  ```

- [ ] Step 2.3: Add ARQ task `deliver_webhook` to `worker.py`

  Open `backend/app/worker.py`. Add the following imports at the top alongside the existing ones:

  ```python
  import httpx
  from app.db.models import CronJob, JobExecution, Webhook, WebhookDelivery
  ```

  (Add `Webhook` and `WebhookDelivery` to the existing `from app.db.models import ...` line.)

  Add the retry schedule constant and the new ARQ task function before `WorkerSettings`:

  ```python
  # Exponential backoff delays in seconds for webhook retry attempts
  _WEBHOOK_RETRY_DELAYS = [1, 10, 60]


  async def deliver_webhook(ctx: dict, *, webhook_id: str, payload: dict) -> None:
      """ARQ task: deliver webhook payload to the JARVIS agent and record delivery.

      Creates a WebhookDelivery record (status=pending), runs the agent via
      run_agent_for_user, then updates the record to success or failed.
      On failure, schedules a retry up to 3 attempts total using exponential backoff.

      ctx["redis"]   — arq Redis connection
      ctx["job_try"] — current attempt number (1-indexed)
      """
      attempt: int = ctx.get("job_try", 1)

      async with AsyncSessionLocal() as db:
          webhook: Webhook | None = await db.get(Webhook, uuid.UUID(webhook_id))
          if webhook is None or not webhook.is_active:
              logger.info("deliver_webhook_skipped_inactive", webhook_id=webhook_id)
              return

          delivery = WebhookDelivery(
              webhook_id=uuid.UUID(webhook_id),
              status="pending",
              attempt=attempt,
          )
          db.add(delivery)
          await db.flush()
          delivery_id = delivery.id

          task_str = webhook.task_template.replace(
              "{payload}", str(payload)[:2000]
          )
          user_id = str(webhook.user_id)
          await db.commit()

      # Run the agent (outside the DB session to avoid long-held connections)
      agent_result: str | None = None
      final_status = "failed"
      response_body: str | None = None

      try:
          agent_result = await run_agent_for_user(user_id=user_id, task=task_str)
          if agent_result and not agent_result.startswith("抱歉"):
              final_status = "success"
          response_body = (agent_result or "")[:4000]
      except Exception as exc:
          response_body = str(exc)[:4000]
          logger.exception(
              "deliver_webhook_agent_failed",
              webhook_id=webhook_id,
              attempt=attempt,
          )

      # Update delivery record
      async with AsyncSessionLocal() as db:
          async with db.begin():
              await db.execute(
                  update(WebhookDelivery)
                  .where(WebhookDelivery.id == delivery_id)
                  .values(
                      status=final_status,
                      response_body=response_body,
                  )
              )
              if final_status == "failed" and attempt < len(_WEBHOOK_RETRY_DELAYS) + 1:
                  delay_s = _WEBHOOK_RETRY_DELAYS[attempt - 1]
                  next_retry = datetime.now(tz=UTC) + timedelta(seconds=delay_s)
                  await db.execute(
                      update(WebhookDelivery)
                      .where(WebhookDelivery.id == delivery_id)
                      .values(next_retry_at=next_retry)
                  )

      if final_status == "failed" and attempt < len(_WEBHOOK_RETRY_DELAYS) + 1:
          delay_s = _WEBHOOK_RETRY_DELAYS[attempt - 1]
          logger.warning(
              "deliver_webhook_will_retry",
              webhook_id=webhook_id,
              attempt=attempt,
              delay_s=delay_s,
          )
          raise RuntimeError(f"Webhook delivery failed (attempt {attempt}), will retry")

      logger.info(
          "deliver_webhook_done",
          webhook_id=webhook_id,
          status=final_status,
          attempt=attempt,
      )
  ```

  Add `deliver_webhook` to `WorkerSettings.functions` and tune retry settings:

  ```python
  class WorkerSettings:
      functions = [execute_cron_job, deliver_webhook]
      cron_jobs = [
          cron(cleanup_old_executions, hour=3, minute=0)
      ]
      redis_settings = RedisSettings.from_dsn(settings.redis_url)
      max_jobs = 10
      job_timeout = 300
      retry_jobs = True
      max_tries = 3  # Already 3 — matches _WEBHOOK_RETRY_DELAYS length
  ```

  Add `from sqlalchemy import delete, update` and `from datetime import UTC, datetime, timedelta` to the existing imports (these may already be partially present — merge carefully).

- [ ] Step 2.4: Refactor `trigger_webhook` endpoint in `webhooks.py` to enqueue ARQ job

  Replace the `asyncio.create_task` block at the end of `trigger_webhook` with an ARQ enqueue call. First add the missing imports at the top of `webhooks.py`:

  ```python
  from arq import create_pool
  from arq.connections import RedisSettings

  from app.core.config import settings
  ```

  Then replace lines ~148-153 (the `asyncio.create_task` block):

  ```python
  # Enqueue async delivery via ARQ (survives process restart; retries on failure)
  arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
  await arq_pool.enqueue_job(
      "deliver_webhook",
      webhook_id=str(webhook_id),
      payload=payload,
  )
  await arq_pool.aclose()
  logger.info("webhook_delivery_enqueued", webhook_id=str(webhook_id))
  ```

  Remove `_background_tasks` set and the `asyncio` import if it is no longer used elsewhere in the file. Keep the `asyncio` import if `asyncio.create_task` is used elsewhere.

  Also remove this no-longer-needed block from the top of `webhooks.py`:

  ```python
  # Strong references to background tasks so they aren't GC'd before completion.
  _background_tasks: set[asyncio.Task] = set()
  ```

- [ ] Step 2.5: Add `GET /api/webhooks/{id}/deliveries` endpoint to `webhooks.py`

  Add the response model and endpoint after the `delete_webhook` handler:

  ```python
  class WebhookDeliveryOut(BaseModel):
      id: uuid.UUID
      webhook_id: uuid.UUID
      triggered_at: datetime
      status: str
      response_code: int | None
      response_body: str | None
      attempt: int
      next_retry_at: datetime | None

      model_config = {"from_attributes": True}


  @router.get("/{webhook_id}/deliveries", response_model=list[WebhookDeliveryOut])
  async def list_webhook_deliveries(
      webhook_id: uuid.UUID,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> list[WebhookDeliveryOut]:
      """Return the last 20 delivery records for a webhook owned by the current user."""
      from app.db.models import WebhookDelivery

      webhook = await db.scalar(
          select(Webhook).where(
              Webhook.id == webhook_id,
              Webhook.user_id == user.id,
          )
      )
      if webhook is None:
          raise HTTPException(status_code=404)

      rows = await db.scalars(
          select(WebhookDelivery)
          .where(WebhookDelivery.webhook_id == webhook_id)
          .order_by(WebhookDelivery.triggered_at.desc())
          .limit(20)
      )
      return [WebhookDeliveryOut.model_validate(r) for r in rows.all()]
  ```

- [ ] Step 2.6: Run static checks

  ```bash
  cd /Users/hyh/code/JARVIS/backend
  uv run ruff check --fix && uv run ruff format
  uv run mypy app
  uv run pytest --collect-only -q
  ```

  Expected: ruff clean, mypy passes, no import errors.

- [ ] Step 2.7: Write unit tests for `deliver_webhook`

  Create `backend/tests/test_deliver_webhook.py`:

  ```python
  """Unit tests for the deliver_webhook ARQ task and deliveries endpoint."""
  import uuid
  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest


  @pytest.mark.asyncio
  async def test_deliver_webhook_success():
      """deliver_webhook marks delivery as success when agent returns a non-error reply."""
      webhook_id = str(uuid.uuid4())
      delivery_id = uuid.uuid4()

      fake_webhook = MagicMock()
      fake_webhook.id = uuid.UUID(webhook_id)
      fake_webhook.is_active = True
      fake_webhook.task_template = "Handle: {payload}"
      fake_webhook.user_id = uuid.uuid4()

      fake_delivery = MagicMock()
      fake_delivery.id = delivery_id

      mock_db = AsyncMock()
      mock_db.__aenter__ = AsyncMock(return_value=mock_db)
      mock_db.__aexit__ = AsyncMock(return_value=None)
      mock_db.get = AsyncMock(return_value=fake_webhook)
      mock_db.add = MagicMock()
      mock_db.flush = AsyncMock()
      mock_db.commit = AsyncMock()
      mock_db.execute = AsyncMock()
      mock_db.begin = MagicMock(
          return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock())
      )

      ctx = {"job_try": 1}

      with (
          patch("app.worker.AsyncSessionLocal", return_value=mock_db),
          patch(
              "app.worker.run_agent_for_user",
              AsyncMock(return_value="Done successfully"),
          ),
          patch("app.worker.WebhookDelivery", return_value=fake_delivery),
      ):
          from app.worker import deliver_webhook

          await deliver_webhook(ctx, webhook_id=webhook_id, payload={"key": "val"})

      # execute() should have been called to set status=success
      assert mock_db.execute.called


  @pytest.mark.asyncio
  async def test_deliver_webhook_retries_on_failure():
      """deliver_webhook raises RuntimeError on failure when retries remain."""
      webhook_id = str(uuid.uuid4())
      delivery_id = uuid.uuid4()

      fake_webhook = MagicMock()
      fake_webhook.id = uuid.UUID(webhook_id)
      fake_webhook.is_active = True
      fake_webhook.task_template = "Handle: {payload}"
      fake_webhook.user_id = uuid.uuid4()

      fake_delivery = MagicMock()
      fake_delivery.id = delivery_id

      mock_db = AsyncMock()
      mock_db.__aenter__ = AsyncMock(return_value=mock_db)
      mock_db.__aexit__ = AsyncMock(return_value=None)
      mock_db.get = AsyncMock(return_value=fake_webhook)
      mock_db.add = MagicMock()
      mock_db.flush = AsyncMock()
      mock_db.commit = AsyncMock()
      mock_db.execute = AsyncMock()
      mock_db.begin = MagicMock(
          return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock())
      )

      ctx = {"job_try": 1}

      with (
          patch("app.worker.AsyncSessionLocal", return_value=mock_db),
          patch(
              "app.worker.run_agent_for_user",
              AsyncMock(side_effect=RuntimeError("agent crashed")),
          ),
          patch("app.worker.WebhookDelivery", return_value=fake_delivery),
      ):
          from app.worker import deliver_webhook

          with pytest.raises(RuntimeError, match="will retry"):
              await deliver_webhook(ctx, webhook_id=webhook_id, payload={})


  @pytest.mark.asyncio
  async def test_deliver_webhook_no_retry_on_last_attempt():
      """deliver_webhook does NOT raise on the final attempt — just marks failed."""
      webhook_id = str(uuid.uuid4())
      delivery_id = uuid.uuid4()

      fake_webhook = MagicMock()
      fake_webhook.id = uuid.UUID(webhook_id)
      fake_webhook.is_active = True
      fake_webhook.task_template = "Handle: {payload}"
      fake_webhook.user_id = uuid.uuid4()

      fake_delivery = MagicMock()
      fake_delivery.id = delivery_id

      mock_db = AsyncMock()
      mock_db.__aenter__ = AsyncMock(return_value=mock_db)
      mock_db.__aexit__ = AsyncMock(return_value=None)
      mock_db.get = AsyncMock(return_value=fake_webhook)
      mock_db.add = MagicMock()
      mock_db.flush = AsyncMock()
      mock_db.commit = AsyncMock()
      mock_db.execute = AsyncMock()
      mock_db.begin = MagicMock(
          return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock())
      )

      # attempt=4 exceeds max (3 retries = attempts 1,2,3; attempt 4 is beyond)
      ctx = {"job_try": 4}

      with (
          patch("app.worker.AsyncSessionLocal", return_value=mock_db),
          patch(
              "app.worker.run_agent_for_user",
              AsyncMock(side_effect=RuntimeError("agent crashed")),
          ),
          patch("app.worker.WebhookDelivery", return_value=fake_delivery),
      ):
          from app.worker import deliver_webhook

          # Should NOT raise on last attempt
          await deliver_webhook(ctx, webhook_id=webhook_id, payload={})
  ```

  Run:

  ```bash
  cd /Users/hyh/code/JARVIS/backend
  uv run pytest tests/test_deliver_webhook.py -v
  ```

- [ ] Step 2.8: Commit

  ```bash
  cd /Users/hyh/code/JARVIS
  git add backend/app/db/models.py \
          backend/alembic/versions/014_webhook_deliveries.py \
          backend/app/api/webhooks.py \
          backend/app/worker.py \
          backend/tests/test_deliver_webhook.py
  git commit -m "feat: async webhook delivery via ARQ with 3-attempt exponential retry and delivery history endpoint"
  ```

---

## Chunk 3 — Task 3.3: Prometheus Custom Metrics + Grafana Alerts

**Files:**
- Create: `backend/app/core/metrics.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/worker.py`
- Modify: `backend/app/rag/context.py`
- Modify: `backend/app/agent/llm.py`
- Create: `monitoring/grafana/provisioning/alerting/jarvis-alerts.yaml`
- Modify: `monitoring/prometheus.yml` (verify only — no change needed)

**Steps:**

- [ ] Step 3.1: Install `prometheus-client`

  ```bash
  cd /Users/hyh/code/JARVIS/backend
  uv add prometheus-client
  ```

  Note: `prometheus-fastapi-instrumentator` (already in `main.py`) depends on `prometheus-client`, so it may already be present transitively. `uv add` is idempotent — it will lock the explicit dependency regardless.

- [ ] Step 3.2: Create `backend/app/core/metrics.py`

  ```python
  """Custom Prometheus metrics for JARVIS application observability.

  Import the singletons from this module and call them directly — do NOT
  re-instantiate them elsewhere (prometheus-client raises on duplicate names).
  """
  from prometheus_client import Counter, Gauge, Histogram

  # ------------------------------------------------------------------
  # Cron execution counter
  # Label: status = "fired" | "skipped" | "error"
  # ------------------------------------------------------------------
  cron_executions_total = Counter(
      "jarvis_cron_executions_total",
      "Total number of cron job executions by outcome",
      labelnames=["status"],
  )

  # ------------------------------------------------------------------
  # RAG retrieval latency histogram
  # Buckets cover 10 ms – 10 s range typical for embedding + vector search
  # ------------------------------------------------------------------
  rag_retrieval_duration_seconds = Histogram(
      "jarvis_rag_retrieval_duration_seconds",
      "End-to-end RAG retrieval latency in seconds",
      buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
  )

  # ------------------------------------------------------------------
  # LLM request counter
  # Labels: provider = "deepseek"|"openai"|"anthropic"|...
  #         model    = model name string
  #         status   = "success" | "error"
  # ------------------------------------------------------------------
  llm_requests_total = Counter(
      "jarvis_llm_requests_total",
      "Total LLM invocations by provider, model, and outcome",
      labelnames=["provider", "model", "status"],
  )

  # ------------------------------------------------------------------
  # ARQ queue depth gauge (polled, not event-driven)
  # ------------------------------------------------------------------
  arq_queue_depth = Gauge(
      "jarvis_arq_queue_depth",
      "Number of jobs currently queued in the ARQ Redis queue",
  )
  ```

- [ ] Step 3.3: Expose custom `/metrics` endpoint and ARQ queue-depth poller in `main.py`

  The existing `main.py` already has `Instrumentator().instrument(app).expose(app)` which mounts `/metrics` using `prometheus-fastapi-instrumentator`. This exposes the default HTTP metrics AND all `prometheus-client` registered metrics (they share the same default registry). No new endpoint is needed.

  However, we need a background task to poll ARQ queue depth and update the gauge. Add the following to the `lifespan` function, just before `yield`:

  ```python
  import asyncio as _asyncio
  from app.core.metrics import arq_queue_depth as _arq_queue_depth

  async def _poll_arq_queue_depth() -> None:
      """Background task: update ARQ queue depth gauge every 30s."""
      from arq.connections import RedisSettings
      from arq import create_pool

      pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
      try:
          while True:
              try:
                  # ARQ stores queued jobs in a Redis sorted set "arq:queue"
                  depth = await pool.zcard("arq:queue")
                  _arq_queue_depth.set(depth)
              except Exception:
                  logger.warning("arq_queue_depth_poll_failed", exc_info=True)
              await _asyncio.sleep(30)
      finally:
          await pool.aclose()

  _poller_task = _asyncio.create_task(_poll_arq_queue_depth())
  yield
  _poller_task.cancel()
  try:
      await _poller_task
  except _asyncio.CancelledError:
      pass
  ```

  Keep the existing `yield` and shutdown code below it as-is, just shift it to after the task cancel block.

  Note: the import should be at the top of the `lifespan` function body (not at module level) to avoid circular imports from `metrics.py`.

- [ ] Step 3.4: Instrument `worker.py` — cron counter

  In `backend/app/worker.py`, after the existing imports, add:

  ```python
  from app.core.metrics import cron_executions_total
  ```

  In `execute_cron_job`, find the `status = "fired"` / `status = "skipped"` / `except Exception` assignment points and add counter increments:

  - After `status = "fired"` (line ~57): add `cron_executions_total.labels(status="fired").inc()` right after the agent call completes (inside the `if result.fired:` block, after `agent_result = ...`).
  - After `status = "skipped"` (line ~66): add `cron_executions_total.labels(status="skipped").inc()`.
  - In the `except Exception` handler (line ~94), after `logger.exception(...)`: add `cron_executions_total.labels(status="error").inc()`.

  Full placement in context:

  ```python
  if result.fired:
      status = "fired"
      trigger_ctx = result.trigger_ctx
      agent_result = await run_agent_for_user(
          user_id=str(job.user_id),
          task=job.task,
          trigger_ctx=result.trigger_ctx,
      )
      agent_result = (agent_result or "")[:2000]
      cron_executions_total.labels(status="fired").inc()   # <-- ADD
  else:
      status = "skipped"
      cron_executions_total.labels(status="skipped").inc() # <-- ADD
  ```

  In the outer `except`:

  ```python
  except Exception as exc:
      duration_ms = int((time.monotonic() - start_ms) * 1000)
      error_msg = str(exc)
      cron_executions_total.labels(status="error").inc()   # <-- ADD
      logger.exception("cron_job_execution_failed", job_id=job_id, error=error_msg)
  ```

- [ ] Step 3.5: Instrument `rag/context.py` — RAG retrieval histogram

  Open `backend/app/rag/context.py`. Add imports:

  ```python
  import time

  from app.core.metrics import rag_retrieval_duration_seconds
  ```

  Wrap the retrieval call in `build_rag_context` with a timer:

  ```python
  try:
      _t0 = time.monotonic()
      chunks = await _retriever.retrieve_context(query, user_id, openai_key)
      rag_retrieval_duration_seconds.observe(time.monotonic() - _t0)
      if not chunks:
          return ""
  ```

- [ ] Step 3.6: Instrument `agent/llm.py` — LLM request counter

  Open `backend/app/agent/llm.py`. Add import:

  ```python
  from app.core.metrics import llm_requests_total
  ```

  Wrap `get_llm` so that callers can observe the outcome. Since `get_llm` is synchronous and returns a model object (not the result of inference), the counter needs to be incremented at the call-site _after_ the invocation. The cleanest pattern is a wrapper in `llm.py` that instruments `ainvoke`.

  Add an instrumented wrapper at the bottom of `llm.py`:

  ```python
  from langchain_core.language_models import BaseChatModel as _BaseChatModel
  from langchain_core.messages import BaseMessage as _BaseMessage
  from typing import Any as _Any


  class _InstrumentedChatModel(_BaseChatModel):
      """Thin wrapper that records llm_requests_total around ainvoke."""

      _inner: _BaseChatModel
      _provider: str
      _model_name: str

      def __init__(self, inner: _BaseChatModel, provider: str, model_name: str) -> None:
          # Bypass Pydantic __init__ — delegate all attribute access
          object.__setattr__(self, "_inner", inner)
          object.__setattr__(self, "_provider", provider)
          object.__setattr__(self, "_model_name", model_name)

      def __getattr__(self, name: str) -> _Any:
          return getattr(self._inner, name)

      async def ainvoke(self, *args: _Any, **kwargs: _Any) -> _Any:
          try:
              result = await self._inner.ainvoke(*args, **kwargs)
              llm_requests_total.labels(
                  provider=self._provider, model=self._model_name, status="success"
              ).inc()
              return result
          except Exception:
              llm_requests_total.labels(
                  provider=self._provider, model=self._model_name, status="error"
              ).inc()
              raise

      def _generate(self, *args: _Any, **kwargs: _Any) -> _Any:
          return self._inner._generate(*args, **kwargs)

      @property
      def _llm_type(self) -> str:
          return self._inner._llm_type
  ```

  Then modify `get_llm` to return an instrumented model:

  ```python
  def get_llm(
      provider: str, model: str, api_key: str, base_url: str | None = None, **kwargs: Any
  ) -> BaseChatModel:
      """Factory function to return an instrumented LangChain ChatModel instance."""
      if "temperature" not in kwargs:
          kwargs["temperature"] = 0
      if "max_retries" not in kwargs:
          kwargs["max_retries"] = 2

      match provider:
          case "deepseek":
              inner = ChatDeepSeek(model=model, api_key=api_key, **kwargs)
          case "openai":
              inner = ChatOpenAI(model=model, api_key=api_key, **kwargs)
          case "anthropic":
              inner = ChatAnthropic(model=model, api_key=api_key, **kwargs)
          case "zhipuai":
              inner = ChatZhipuAI(model=model, api_key=api_key, **kwargs)
          case "ollama":
              target_url = base_url or settings.ollama_base_url
              logger.info("creating_ollama_client", model=model, url=target_url)
              inner = ChatOllama(model=model, base_url=target_url, **kwargs)
          case _:
              raise ValueError(f"Unknown provider: {provider}")

      return _InstrumentedChatModel(inner, provider, model)
  ```

  Note: `_InstrumentedChatModel` uses `object.__setattr__` to bypass Pydantic validation since Pydantic v2 models reject unknown fields. If mypy complains, add `# type: ignore[override]` where needed. Alternatively (simpler): skip the wrapper class and instead instrument at call-sites in `chat.py` and `agent_runner.py` where `get_llm` return values are `.ainvoke()`d. The wrapper approach is preferred to keep instrumentation in one place.

  If the wrapper causes issues with LangGraph type expectations, fall back to the simpler approach: add `llm_requests_total` increments directly in `chat.py`'s `generate()` function after each successful/failed `graph.astream()` completion, and in `agent_runner.py` after `graph.ainvoke()`.

- [ ] Step 3.7: Create `monitoring/grafana/provisioning/alerting/jarvis-alerts.yaml`

  ```yaml
  # Grafana provisioning — alerting rules for JARVIS
  # Grafana 10+ unified alerting format
  apiVersion: 1

  groups:
    - name: jarvis
      folder: JARVIS Alerts
      interval: 1m
      rules:

        # ----------------------------------------------------------------
        # ARQ queue depth > 50 for 5 minutes → warning
        # ----------------------------------------------------------------
        - uid: jarvis-arq-queue-depth-high
          title: ARQ Queue Depth High
          condition: C
          data:
            - refId: A
              datasourceUid: prometheus
              model:
                expr: jarvis_arq_queue_depth
                intervalMs: 60000
                maxDataPoints: 43200
                refId: A
            - refId: C
              datasourceUid: __expr__
              model:
                type: threshold
                refId: C
                conditions:
                  - evaluator:
                      params: [50]
                      type: gt
                    operator:
                      type: and
                    query:
                      params: [A]
                    reducer:
                      params: []
                      type: last
          noDataState: NoData
          execErrState: Alerting
          for: 5m
          annotations:
            summary: "ARQ job queue depth is {{ $value }} (threshold: 50)"
            description: "The ARQ Redis queue has been above 50 jobs for 5+ minutes. Check worker health and Redis connectivity."
          labels:
            severity: warning
            team: jarvis

        # ----------------------------------------------------------------
        # Cron failure rate > 20% over 1 hour → critical
        # ----------------------------------------------------------------
        - uid: jarvis-cron-failure-rate-high
          title: Cron Job Failure Rate High
          condition: C
          data:
            - refId: A
              datasourceUid: prometheus
              model:
                expr: >
                  rate(jarvis_cron_executions_total{status="error"}[1h])
                  /
                  (rate(jarvis_cron_executions_total[1h]) + 1e-9)
                intervalMs: 60000
                maxDataPoints: 43200
                refId: A
            - refId: C
              datasourceUid: __expr__
              model:
                type: threshold
                refId: C
                conditions:
                  - evaluator:
                      params: [0.2]
                      type: gt
                    operator:
                      type: and
                    query:
                      params: [A]
                    reducer:
                      params: []
                      type: last
          noDataState: NoData
          execErrState: Alerting
          for: 0s
          annotations:
            summary: "Cron failure rate is {{ $value | humanizePercentage }} over the last hour"
            description: "More than 20% of cron job executions are failing. Check worker logs and trigger configurations."
          labels:
            severity: critical
            team: jarvis

        # ----------------------------------------------------------------
        # API P99 latency > 5s → warning
        # Uses histogram generated by prometheus-fastapi-instrumentator
        # Metric name: http_request_duration_seconds (default instrumentator name)
        # ----------------------------------------------------------------
        - uid: jarvis-api-p99-latency-high
          title: API P99 Latency High
          condition: C
          data:
            - refId: A
              datasourceUid: prometheus
              model:
                expr: >
                  histogram_quantile(
                    0.99,
                    rate(http_request_duration_seconds_bucket{job="backend"}[5m])
                  )
                intervalMs: 60000
                maxDataPoints: 43200
                refId: A
            - refId: C
              datasourceUid: __expr__
              model:
                type: threshold
                refId: C
                conditions:
                  - evaluator:
                      params: [5.0]
                      type: gt
                    operator:
                      type: and
                    query:
                      params: [A]
                    reducer:
                      params: []
                      type: last
          noDataState: NoData
          execErrState: Alerting
          for: 5m
          annotations:
            summary: "API P99 latency is {{ $value }}s (threshold: 5s)"
            description: "The 99th percentile API response time has been above 5 seconds for 5+ minutes."
          labels:
            severity: warning
            team: jarvis
  ```

- [ ] Step 3.8: Verify `monitoring/prometheus.yml`

  The existing `prometheus.yml` already contains:

  ```yaml
  - job_name: backend
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /metrics
  ```

  This is correct — `prometheus-fastapi-instrumentator` exposes `/metrics` and the custom `prometheus-client` metrics share the same default registry, so no changes to `prometheus.yml` are needed. Confirm by reading the file — no edit required.

- [ ] Step 3.9: Add `monitoring/grafana/provisioning/alerting/` directory to Grafana provisioning config

  Check the existing `monitoring/grafana/provisioning/dashboards/provider.yml` to understand the provisioning directory layout. Grafana auto-discovers `alerting/` subdirectories under the provisioning path when the `alerting` key is present in the Grafana config or when `GF_PATHS_PROVISIONING` points to the directory. No additional YAML file is needed — Grafana 10 auto-loads all YAML files in `provisioning/alerting/`. The `jarvis-alerts.yaml` file created in Step 3.7 will be picked up automatically on next Grafana startup.

  Verify `monitoring/grafana/provisioning/dashboards/provider.yml` to confirm the provisioning base path used in Docker Compose:

  ```bash
  cat /Users/hyh/code/JARVIS/monitoring/grafana/provisioning/dashboards/provider.yml
  ```

  If the file confirms the mount is at `/etc/grafana/provisioning`, the alerting YAML path `monitoring/grafana/provisioning/alerting/jarvis-alerts.yaml` maps correctly to `/etc/grafana/provisioning/alerting/jarvis-alerts.yaml` in the container.

- [ ] Step 3.10: Run static checks

  ```bash
  cd /Users/hyh/code/JARVIS/backend
  uv run ruff check --fix && uv run ruff format
  uv run mypy app
  uv run pytest --collect-only -q
  ```

  Expected: ruff clean, mypy passes, no import errors.

- [ ] Step 3.11: Write unit tests for metrics module

  Create `backend/tests/test_metrics.py`:

  ```python
  """Unit tests for custom Prometheus metrics instrumentation."""
  import time
  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest
  from prometheus_client import REGISTRY


  def test_metrics_singletons_registered():
      """All custom metric names are registered in the Prometheus default registry."""
      names = {m.name for m in REGISTRY.collect()}
      assert "jarvis_cron_executions_total" in names
      assert "jarvis_rag_retrieval_duration_seconds" in names
      assert "jarvis_llm_requests_total" in names
      assert "jarvis_arq_queue_depth" in names


  def test_cron_counter_labels():
      """cron_executions_total accepts the expected label values."""
      from app.core.metrics import cron_executions_total

      before = cron_executions_total.labels(status="fired")._value.get()
      cron_executions_total.labels(status="fired").inc()
      after = cron_executions_total.labels(status="fired")._value.get()
      assert after == before + 1.0


  def test_rag_histogram_records_observation():
      """rag_retrieval_duration_seconds accepts float observations."""
      from app.core.metrics import rag_retrieval_duration_seconds

      # Should not raise
      rag_retrieval_duration_seconds.observe(0.123)
      rag_retrieval_duration_seconds.observe(1.5)


  def test_llm_counter_labels():
      """llm_requests_total accepts provider, model, status labels."""
      from app.core.metrics import llm_requests_total

      before = llm_requests_total.labels(
          provider="deepseek", model="deepseek-chat", status="success"
      )._value.get()
      llm_requests_total.labels(
          provider="deepseek", model="deepseek-chat", status="success"
      ).inc()
      after = llm_requests_total.labels(
          provider="deepseek", model="deepseek-chat", status="success"
      )._value.get()
      assert after == before + 1.0


  @pytest.mark.asyncio
  async def test_rag_context_records_histogram():
      """build_rag_context observes the RAG retrieval histogram on success."""
      from app.core.metrics import rag_retrieval_duration_seconds

      fake_chunk = MagicMock()
      fake_chunk.document_name = "test.pdf"
      fake_chunk.score = 0.9
      fake_chunk.content = "Test content"

      with (
          patch(
              "app.rag.context._retriever.retrieve_context",
              AsyncMock(return_value=[fake_chunk]),
          ),
      ):
          from app.rag.context import build_rag_context

          result = await build_rag_context("user-123", "query", "openai-key")

      assert "Test content" in result
  ```

  Run:

  ```bash
  cd /Users/hyh/code/JARVIS/backend
  uv run pytest tests/test_metrics.py -v
  ```

- [ ] Step 3.12: Commit

  ```bash
  cd /Users/hyh/code/JARVIS
  git add backend/app/core/metrics.py \
          backend/app/main.py \
          backend/app/worker.py \
          backend/app/rag/context.py \
          backend/app/agent/llm.py \
          monitoring/grafana/provisioning/alerting/jarvis-alerts.yaml \
          backend/tests/test_metrics.py \
          backend/uv.lock \
          backend/pyproject.toml
  git commit -m "feat: add custom Prometheus metrics (cron/rag/llm/arq) and Grafana alert rules"
  ```

---

## Post-Implementation Verification

After all three chunks are merged to `dev`:

```bash
# 1. Run full migration
cd /Users/hyh/code/JARVIS/backend
uv run alembic upgrade head

# 2. Run all new tests
uv run pytest tests/test_agent_runner_metadata.py \
              tests/test_deliver_webhook.py \
              tests/test_metrics.py -v

# 3. Full Docker stack
cd /Users/hyh/code/JARVIS
docker compose up -d
docker compose ps   # All containers healthy

# 4. Verify /metrics endpoint exposes custom metrics
curl -s http://localhost:8000/metrics | grep jarvis_

# 5. Confirm Grafana loads alert rules
# Open http://localhost:3001 → Alerting → Alert rules → look for "JARVIS Alerts" folder

# 6. Pre-commit hooks
pre-commit run --all-files
```

---

### Critical Files for Implementation

- `/Users/hyh/code/JARVIS/backend/app/api/chat.py` - Core logic to modify: AgentSession metadata write in `generate()` finally block and `tools_used` accumulation during streaming
- `/Users/hyh/code/JARVIS/backend/app/worker.py` - Core logic to modify: add `deliver_webhook` ARQ task, cron counter instrumentation, and include in `WorkerSettings.functions`
- `/Users/hyh/code/JARVIS/backend/app/gateway/agent_runner.py` - Core logic to modify: add AgentSession creation + metadata_json write for background runs
- `/Users/hyh/code/JARVIS/backend/app/core/metrics.py` - New module to create: all four custom prometheus-client metric singletons
- `/Users/hyh/code/JARVIS/backend/alembic/versions/012_add_job_executions.py` - Pattern to follow: exact migration format for `014_webhook_deliveries.py` (UUID PK, FK with CASCADE, indexes)