"""Standalone agent runner for background tasks (cron jobs, webhook triggers)."""

from __future__ import annotations

import uuid

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from app.agent.graph import create_graph
from app.agent.persona import build_system_prompt
from app.agent.state import AgentState
from app.core.config import settings
from app.core.permissions import DEFAULT_ENABLED_TOOLS
from app.core.security import resolve_api_key, resolve_api_keys
from app.db.models import Conversation, Message, UserSettings
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)


async def run_agent_for_user(user_id: str, task: str) -> str:
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

            # Persist human message BEFORE invoking agent so its timestamp
            # precedes the AI message in chronological ordering.
            human_msg = Message(conversation_id=conv.id, role="human", content=task)
            db.add(human_msg)
            await db.flush()

            lc_messages = [
                SystemMessage(content=build_system_prompt(persona)),
                HumanMessage(content=task),
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

            result = await graph.ainvoke(AgentState(messages=lc_messages))
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
