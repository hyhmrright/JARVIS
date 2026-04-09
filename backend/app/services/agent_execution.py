"""Unified agent execution service.

This service owns the execution path for both the REST API (non-streaming)
and the multi-channel Gateway.
"""

from __future__ import annotations

import uuid

import structlog
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.compressor import compact_messages
from app.agent.graph import create_graph
from app.agent.persona import build_system_prompt
from app.agent.state import AgentState
from app.core.config import settings
from app.core.permissions import DEFAULT_ENABLED_TOOLS
from app.core.security import resolve_api_key, resolve_api_keys
from app.db.models import Conversation, Message, UserSettings
from app.rag.context import build_rag_context

logger = structlog.get_logger(__name__)


class AgentExecutionService:
    """阻塞式执行 JARVIS Agent 图。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_blocking(
        self,
        user_id: uuid.UUID,
        content: str,
        conversation_id: uuid.UUID | None = None,
        channel: str = "api",
    ) -> str:
        """运行 Agent 并返回最终回复文本。"""
        # 1. 加载配置
        user_settings = await self.db.scalar(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        provider = user_settings.model_provider if user_settings else "deepseek"
        model_name = user_settings.model_name if user_settings else "deepseek-chat"
        raw_keys = user_settings.api_keys if user_settings else {}
        enabled_tools = (
            user_settings.enabled_tools
            if user_settings and user_settings.enabled_tools is not None
            else DEFAULT_ENABLED_TOOLS
        )
        persona_override = user_settings.persona_override if user_settings else None

        api_keys = resolve_api_keys(provider, raw_keys)
        if not api_keys:
            return "No API key configured. Please set one in Settings."

        # 2. 准备会话
        conv: Conversation | None = None
        if conversation_id:
            conv = await self.db.get(Conversation, conversation_id)

        if conv is None:
            conv = Conversation(user_id=user_id, title=f"Conversation ({channel})")
            self.db.add(conv)
            await self.db.flush()

        assert conv is not None

        # 3. 持久化用户消息
        self.db.add(Message(conversation_id=conv.id, role="human", content=content))
        await self.db.flush()

        # 4. 构建历史消息
        rows = await self.db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at)
        )
        role_map = {"human": HumanMessage, "ai": AIMessage}
        lc_messages: list[BaseMessage] = [
            SystemMessage(content=build_system_prompt(persona_override))
        ]
        for row in rows.all():
            cls = role_map.get(row.role)
            if cls:
                lc_messages.append(cls(content=row.content))

        # 5. RAG 上下文
        openai_key = resolve_api_key("openai", raw_keys)
        rag_context = await build_rag_context(str(user_id), content, openai_key)
        if rag_context:
            lc_messages.insert(1, SystemMessage(content=rag_context))

        # 6. 压缩消息
        try:
            lc_messages = await compact_messages(
                lc_messages, provider=provider, model=model_name, api_key=api_keys[0]
            )
        except Exception:
            logger.warning("execution_compression_failed", exc_info=True)

        # 7. 运行 Graph
        graph = create_graph(
            provider=provider,
            model=model_name,
            api_key=api_keys[0],
            enabled_tools=enabled_tools,
            api_keys=api_keys,
            user_id=str(user_id),
            openai_api_key=openai_key,
            tavily_api_key=settings.tavily_api_key,
            conversation_id=str(conv.id),
        )

        result = await graph.ainvoke(AgentState(messages=lc_messages))
        ai_content = str(result["messages"][-1].content)

        # 8. 持久化 AI 回复
        self.db.add(
            Message(
                conversation_id=conv.id,
                role="ai",
                content=ai_content,
                model_provider=provider,
                model_name=model_name,
            )
        )
        await self.db.commit()

        return ai_content
