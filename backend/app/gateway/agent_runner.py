"""Standalone agent runner for background tasks (cron jobs, webhook triggers)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select, update

from app.agent.graph import create_graph
from app.agent.persona import build_system_prompt
from app.agent.state import AgentState
from app.core.config import settings
from app.core.permissions import DEFAULT_ENABLED_TOOLS
from app.core.security import resolve_api_key, resolve_api_keys
from app.db.models import AgentSession, Conversation, Message, UserSettings
from app.db.session import AsyncSessionLocal
from app.rag.context import build_rag_context

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
    """Execute the JARVIS agent for the given user and task text.

    Creates a new conversation, runs the agent, persists the response,
    and returns the AI reply string.  Returns a descriptive error string
    (never raises) so callers can fire-and-forget safely.
    """
    try:
        async with AsyncSessionLocal() as db:
            us = await db.scalar(
                select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id))
            )
            provider = us.model_provider if us else "deepseek"
            model_name = us.model_name if us else "deepseek-chat"
            raw_keys = us.api_keys if us else {}
            persona = us.persona_override if us else None
            enabled = (
                us.enabled_tools
                if us and us.enabled_tools is not None
                else DEFAULT_ENABLED_TOOLS
            )

            api_keys = resolve_api_keys(provider, raw_keys)
            if not api_keys:
                logger.warning("agent_runner_no_api_keys", user_id=user_id)
                return "未配置可用的 API Key，请先在设置页面中添加。"

            conv = Conversation(
                user_id=uuid.UUID(user_id),
                title=f"Auto: {task[:60]}",
            )
            db.add(conv)
            await db.flush()

            # Build full task with optional trigger context prefix
            ctx_block = format_trigger_context(trigger_ctx)
            full_task = f"{ctx_block}\n\n[用户任务]\n{task}" if ctx_block else task

            # RAG: inject relevant knowledge-base context
            openai_key = resolve_api_key("openai", raw_keys)
            rag_context = await build_rag_context(user_id, full_task, openai_key)

            # Persist human message BEFORE invoking agent so its timestamp
            # precedes the AI message in chronological ordering.
            human_msg = Message(
                conversation_id=conv.id, role="human", content=full_task
            )
            db.add(human_msg)
            await db.flush()

            system_content = build_system_prompt(persona)
            lc_messages = [
                SystemMessage(content=system_content),
                *([SystemMessage(content=rag_context)] if rag_context else []),
                HumanMessage(content=full_task),
            ]

            mcp_tools: list = []
            if "mcp" in enabled:
                from app.tools.mcp_client import (
                    create_mcp_tools,
                    parse_mcp_configs,
                )

                mcp_tools = await create_mcp_tools(
                    parse_mcp_configs(settings.mcp_servers_json)
                )

            graph = create_graph(
                provider=provider,
                model=model_name,
                api_key=api_keys[0],
                enabled_tools=enabled,
                api_keys=api_keys,
                user_id=user_id,
                openai_api_key=resolve_api_key("openai", raw_keys),
                tavily_api_key=settings.tavily_api_key,
                mcp_tools=mcp_tools,
                conversation_id=str(conv.id),
            )

            # Create AgentSession for this background run
            agent_session_id: uuid.UUID | None = None
            try:
                ag = AgentSession(
                    conversation_id=conv.id,
                    agent_type="main",
                    status="active",
                )
                db.add(ag)
                await db.flush()
                agent_session_id = ag.id
            except Exception:
                logger.warning("agent_session_create_failed", exc_info=True)

            run_error = False
            result = None
            try:
                result = await graph.ainvoke(AgentState(messages=lc_messages))
            except Exception:
                run_error = True
                raise
            finally:
                if agent_session_id:
                    try:
                        trigger_type = (
                            trigger_ctx.get("trigger_type", "unknown")
                            if trigger_ctx
                            else "unknown"
                        )
                        metadata: dict[str, object] = {
                            "model": model_name,
                            "provider": provider,
                            "tools_used": [],
                            "trigger_type": trigger_type,
                        }
                        async with AsyncSessionLocal() as sess:
                            async with sess.begin():
                                await sess.execute(
                                    update(AgentSession)
                                    .where(AgentSession.id == agent_session_id)
                                    .values(
                                        status="error" if run_error else "completed",
                                        completed_at=datetime.now(UTC),
                                        metadata_json=metadata,
                                    )
                                )
                    except Exception:
                        logger.warning("agent_session_update_failed", exc_info=True)

            ai_content = str(result["messages"][-1].content)

            db.add(
                Message(
                    conversation_id=conv.id,
                    role="ai",
                    content=ai_content,
                    model_provider=provider,
                    model_name=model_name,
                )
            )
            await db.commit()

            logger.info(
                "agent_runner_completed",
                user_id=user_id,
                reply_chars=len(ai_content),
            )
            return ai_content
    except Exception:
        logger.exception("agent_runner_error", user_id=user_id)
        return "抱歉，处理请求时出现错误，请稍后重试。"
