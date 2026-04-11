"""Unified Agent Engine.

Handles configuration loading, RAG context, state management,
and execution (both blocking and streaming) for the JARVIS agent.

Refactored to delegate responsibility to specialized services:
- ContextService: History and RAG
- ConfigService: LLM and Provider configuration
- ToolService: Plugin and MCP tools
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from dataclasses import replace
from typing import Any

import structlog
from langchain_core.messages import (
    ToolMessage,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import create_graph
from app.agent.protocol import (
    AgentEvent,
    ErrorEvent,
    HumanMessageSavedEvent,
    RoutingEvent,
    TextDeltaEvent,
)
from app.agent.router import classify_task
from app.agent.state import AgentState
from app.agent.supervisor import SupervisorState, create_supervisor_graph
from app.api.chat.graph_builder import build_expert_graph
from app.api.chat.sse import (
    extract_token_counts,
    sse_events_from_chunk,
)
from app.core.config import settings
from app.core.llm_config import AgentConfig, ResolvedLLMConfig
from app.core.security import resolve_api_key
from app.db.models import Conversation
from app.services.config_service import ConfigService
from app.services.context_service import ContextService
from app.services.memory_sync import sync_conversation_to_markdown
from app.services.tool_service import ToolService

logger = structlog.get_logger(__name__)


class AgentEngine:
    """JARVIS 核心 Agent 引擎。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.config_service = ConfigService(db)
        self.context_service = ContextService(db)
        self.tool_service = ToolService(db)

    async def run_blocking(
        self,
        user_id: uuid.UUID,
        content: str,
        conversation_id: uuid.UUID | None = None,
        channel: str = "api",
    ) -> str:
        """同步阻塞式运行。"""
        llm = await self.config_service.get_llm_config(user_id)
        conv = await self._ensure_conversation(user_id, conversation_id, channel)

        # 1. 保存用户消息
        user_msg = conv.add_message(role="human", content=content)
        await self.db.flush()

        # 2. 构建消息并运行
        lc_messages = await self.context_service.build_messages(
            user_id, conv, llm, content
        )

        config = AgentConfig(
            llm=llm,
            user_id=str(user_id),
            conversation_id=str(conv.id),
            openai_api_key=resolve_api_key("openai", llm.raw_keys),
            tavily_api_key=settings.tavily_api_key,
        )
        graph = create_graph(config)
        result = await graph.ainvoke(AgentState(messages=lc_messages))
        ai_content = str(result["messages"][-1].content)

        # 3. 保存 AI 回复
        conv.add_message(
            role="ai",
            content=ai_content,
            model_provider=llm.provider,
            model_name=llm.model_name,
            parent_id=user_msg.id,
        )
        await self.db.commit()
        return ai_content

    async def run_streaming(  # noqa: C901
        self,
        user_id: uuid.UUID,
        content: str,
        conversation_id: uuid.UUID,
        is_disconnected_func: Any = None,
        model_override: str | None = None,
    ) -> AsyncGenerator[AgentEvent]:
        """统一的流式运行逻辑。"""
        llm = await self.config_service.get_llm_config(user_id)
        if model_override:
            llm = replace(llm, model_name=model_override)

        user_id_str = str(user_id)
        conv = await self._ensure_conversation(user_id, conversation_id, "chat")

        # 1. 持久化人类消息
        human_msg = conv.add_message(role="human", content=content)
        await self.db.flush()
        human_msg_id = human_msg.id
        yield HumanMessageSavedEvent(human_msg_id=str(human_msg_id))

        # 2. 构建上下文与压缩
        lc_messages = await self.context_service.build_messages(
            user_id, conv, llm, content, compress=True
        )
        compressed_summary = None
        for m in lc_messages:
            m_content = getattr(m, "content", "")
            if isinstance(m_content, str) and m_content.startswith(
                "[Conversation summary]"
            ):
                compressed_summary = m_content
                break

        # 3. 路由与工具加载
        mcp_tools, plugin_tools = await self.tool_service.load_all_tools(
            user_id_str, llm.enabled_tools
        )
        route = await classify_task(
            content, provider=llm.provider, model=llm.model_name, api_key=llm.api_key
        )
        yield RoutingEvent(agent=route)

        # 4. 执行 Graph 循环
        full_content = ""
        last_ai_msg = None
        tools_used: list[str] = []
        stream_error = False

        try:
            if route == "complex":
                # Supervisor 模式
                supervisor = create_supervisor_graph(
                    provider=llm.provider,
                    model=llm.model_name,
                    api_key=llm.api_key,
                    api_keys=llm.api_keys,
                    user_id=user_id_str,
                    openai_api_key=resolve_api_key("openai", llm.raw_keys),
                    tavily_api_key=settings.tavily_api_key,
                    enabled_tools=llm.enabled_tools or [],
                    base_url=llm.base_url,
                )
                tools_used = ["supervisor"]
                final_state = await supervisor.ainvoke(
                    SupervisorState(messages=lc_messages)
                )
                last_ai_msg = final_state["messages"][-1]
                full_content = str(last_ai_msg.content)
                # 模拟流式
                for i in range(0, len(full_content), 50):
                    yield TextDeltaEvent(delta=full_content[i : i + 50])
                    if is_disconnected_func and await is_disconnected_func():
                        return
            else:
                # Expert 模式
                graph = build_expert_graph(
                    route,
                    AgentConfig(
                        llm=llm,
                        user_id=user_id_str,
                        conversation_id=str(conv.id),
                        openai_api_key=resolve_api_key("openai", llm.raw_keys),
                        tavily_api_key=settings.tavily_api_key,
                        mcp_tools=mcp_tools or [],
                        plugin_tools=plugin_tools or [],
                    ),
                )
                async for chunk in graph.astream(AgentState(messages=lc_messages)):
                    if "llm" in chunk:
                        last_ai_msg = chunk["llm"]["messages"][-1]
                    if "tools" in chunk:
                        for tm in chunk["tools"]["messages"]:
                            tm_name = getattr(tm, "name", None)
                            if (
                                isinstance(tm, ToolMessage)
                                and tm_name
                                and tm_name not in tools_used
                            ):
                                tools_used.append(tm_name)

                    events, full_content = sse_events_from_chunk(
                        chunk, full_content, human_msg_id
                    )
                    for e in events:
                        yield e

                    if is_disconnected_func and await is_disconnected_func():
                        return

        except Exception:
            stream_error = True
            logger.exception("engine_stream_error")
            yield ErrorEvent(content="Internal Engine Error")
        finally:
            # 5. 收尾工作
            await self._finalize_stream(
                user_id=user_id,
                conv=conv,
                full_content=full_content,
                last_ai_msg=last_ai_msg,
                parent_id=human_msg_id,
                llm=llm,
                tools_used=tools_used,
                error=stream_error,
                summary=compressed_summary,
            )

    async def _ensure_conversation(
        self, user_id: uuid.UUID, conv_id: uuid.UUID | None, channel: str
    ) -> Conversation:
        if conv_id:
            c = await self.db.get(Conversation, conv_id)
            if c:
                return c
        c = Conversation(user_id=user_id, title=f"Conversation ({channel})")
        self.db.add(c)
        await self.db.flush()
        return c

    async def _finalize_stream(
        self,
        user_id: uuid.UUID,
        conv: Conversation,
        full_content: str,
        last_ai_msg: Any,
        parent_id: uuid.UUID | None,
        llm: ResolvedLLMConfig,
        tools_used: list[str],
        error: bool,
        summary: str | None,
    ) -> None:
        """流式结束后的持久化与清理。"""
        tokens_in, tokens_out = extract_token_counts(last_ai_msg)
        if full_content:
            try:
                conv.add_message(
                    role="ai",
                    content=full_content,
                    model_provider=llm.provider,
                    model_name=llm.model_name,
                    tokens_input=tokens_in,
                    tokens_output=tokens_out,
                    parent_id=parent_id,
                )
                await self.db.commit()
                asyncio.create_task(sync_conversation_to_markdown(conv.id))
            except Exception:
                logger.exception("finalize_persistence_failed")

        logger.info("stream_finalized", conv_id=str(conv.id), error=error)
