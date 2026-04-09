"""Standalone agent runner for background tasks (cron jobs, webhook triggers)."""

from __future__ import annotations

import uuid

import structlog

from app.db.session import AsyncSessionLocal
from app.services.agent_execution import AgentExecutionService

logger = structlog.get_logger(__name__)


def format_trigger_context(trigger_ctx: dict | None) -> str:
    """Format trigger context as a human-readable block for injection into task."""
    if not trigger_ctx:
        return ""
    lines = ["[触发上下文]"]
    trigger_type = trigger_ctx.get("trigger_type", "")
    if detected_at := trigger_ctx.get("detected_at"):
        lines.append(f"检测时间：{detected_at}")
    if trigger_type in ("semantic_watcher", "web_watcher"):
        if target := trigger_ctx.get("target"):
            lines.append(f"监控目标：{target}")
        if summary := trigger_ctx.get("changed_summary"):
            lines.append(f"检测到变化：{summary}")
        if url := trigger_ctx.get("url"):
            lines.append(f"原始页面：{url}")
    elif trigger_type == "email":
        count = trigger_ctx.get("new_email_count", 0)
        lines.append(f"新邮件数量：{count}")
        for i, em in enumerate(trigger_ctx.get("emails", [])[:3], 1):
            lines.append(f"邮件{i}：{em.get('from', '')} — {em.get('subject', '')}")
    return "\n".join(lines)


async def run_agent_for_user(
    user_id: str,
    task: str,
    trigger_ctx: dict | None = None,
) -> str:
    """为给定用户和任务执行 JARVIS Agent。

    由 AgentExecutionService 统一处理配置、会话、消息持久化和 Graph 运行。
    """
    ctx_block = format_trigger_context(trigger_ctx)
    full_task = f"{ctx_block}\n\n[用户任务]\n{task}" if ctx_block else task
    trigger_type = (
        trigger_ctx.get("trigger_type", "unknown") if trigger_ctx else "unknown"
    )

    try:
        async with AsyncSessionLocal() as db:
            service = AgentExecutionService(db)
            # 注意：run_blocking 内部会处理会话创建和消息持久化
            reply = await service.run_blocking(
                user_id=uuid.UUID(user_id),
                content=full_task,
                channel=f"runner:{trigger_type}",
            )

            logger.info(
                "agent_runner_completed",
                user_id=user_id,
                reply_chars=len(reply),
            )
            return reply
    except Exception:
        logger.exception("agent_runner_error", user_id=user_id)
        raise
