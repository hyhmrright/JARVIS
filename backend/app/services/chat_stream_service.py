from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import structlog
from langchain_core.messages import ToolMessage
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.compressor import compact_messages
from app.agent.router import classify_task
from app.agent.state import AgentState
from app.agent.supervisor import SupervisorState, create_supervisor_graph
from app.api.chat.context import ChatContext
from app.api.chat.graph_builder import (
    build_expert_graph,
    load_all_tools,
)
from app.api.chat.sse import (
    extract_token_counts,
    serialize_tool_message,
    sse_events_from_chunk,
    tool_call_signature,
)
from app.core.config import settings
from app.core.llm_config import AgentConfig, ResolvedLLMConfig
from app.db.models import AgentSession, Conversation, Message
from app.db.session import AsyncSessionLocal
from app.services.memory_sync import sync_conversation_to_markdown

logger = structlog.get_logger(__name__)


class ChatStreamService:
    """流式 Agent 执行服务，解耦路由逻辑。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_stream(  # noqa: C901
        self,
        ctx: ChatContext,
        llm: ResolvedLLMConfig,
        user_id_str: str,
        is_disconnected_func: Any,
    ) -> AsyncGenerator[dict[str, Any] | str]:
        """执行流式聊天并生成结构化事件。"""
        lc_messages = ctx.lc_messages
        if ctx.human_msg_id:
            yield {"type": "human_msg_saved", "human_msg_id": str(ctx.human_msg_id)}

        # 1. 消息压缩
        compressed_summary = None
        try:
            lc_messages = await compact_messages(
                lc_messages,
                provider=llm.provider,
                model=llm.model_name,
                api_key=llm.api_key,
                base_url=llm.base_url,
            )
            for m in lc_messages:
                content = getattr(m, "content", "")
                if isinstance(content, str) and content.startswith(
                    "[Conversation summary]"
                ):
                    compressed_summary = content
                    break
        except Exception:
            logger.warning("context_compression_failed", exc_info=True)

        # 2. 创建 Agent 会话
        agent_session_id = None
        try:
            async with AsyncSessionLocal() as _init_sess:
                async with _init_sess.begin():
                    ag_sess = AgentSession(
                        conversation_id=ctx.conv_id,
                        agent_type="main",
                        status="active",
                    )
                    _init_sess.add(ag_sess)
                    await _init_sess.flush()
                    agent_session_id = ag_sess.id
        except Exception:
            logger.warning("agent_session_create_failed", exc_info=True)

        # 3. 任务分类与路由
        mcp_tools, plugin_tools = await load_all_tools(user_id_str, llm.enabled_tools)
        route = "simple"
        if not ctx.is_consent:
            route = await classify_task(
                ctx.user_content,
                provider=llm.provider,
                model=llm.model_name,
                api_key=llm.api_key,
                base_url=llm.base_url,
            )
            yield {"type": "routing", "agent": route}

        # 4. 执行 Graph
        full_content = ""
        last_ai_msg = None
        tools_used: list[str] = []
        stream_completed = False
        persisted_parent_id = (
            ctx.human_msg_id if not ctx.is_consent else ctx.parent_message_id
        )
        persisted_tool_batches = set()
        persisted_tool_results = set()
        stream_error = False

        try:
            if route == "complex":
                yield {"type": "status", "message": "正在规划复杂任务..."}
                supervisor = create_supervisor_graph(
                    provider=llm.provider,
                    model=llm.model_name,
                    api_key=llm.api_key,
                    api_keys=llm.api_keys,
                    user_id=user_id_str,
                    openai_api_key=ctx.openai_key,
                    tavily_api_key=settings.tavily_api_key,
                    enabled_tools=llm.enabled_tools,
                    base_url=llm.base_url,
                )
                tools_used = ["supervisor"]
                final_state = await supervisor.ainvoke(
                    SupervisorState(messages=lc_messages)
                )
                msgs = final_state.get("messages", [])
                if msgs:
                    last_ai_msg = msgs[-1]
                    full_content = str(getattr(last_ai_msg, "content", ""))
                    chunk_size = 50
                    for i in range(0, len(full_content), chunk_size):
                        piece = full_content[i : i + chunk_size]
                        is_last = i + chunk_size >= len(full_content)
                        yield {
                            "type": "delta",
                            "delta": piece,
                            "content": full_content if is_last else None,
                        }
                        if await is_disconnected_func():
                            return
                        await asyncio.sleep(0)
            else:
                graph = build_expert_graph(
                    route,
                    AgentConfig(
                        llm=llm,
                        user_id=user_id_str,
                        conversation_id=str(ctx.conv_id),
                        openai_api_key=ctx.openai_key,
                        tavily_api_key=settings.tavily_api_key,
                        mcp_tools=mcp_tools or [],
                        plugin_tools=plugin_tools or [],
                        workflow_dsl=ctx.workflow_dsl,
                    ),
                )
                state = AgentState(messages=lc_messages, approved=ctx.approved)
                async with asyncio.timeout(settings.graph_timeout_seconds):
                    async for chunk in graph.astream(state):
                        if "llm" in chunk:
                            last_ai_msg = chunk["llm"]["messages"][-1]
                            tool_calls = getattr(last_ai_msg, "tool_calls", None) or []
                            sig = tool_call_signature(tool_calls)
                            if tool_calls and sig not in persisted_tool_batches:
                                async with AsyncSessionLocal() as persist_sess:
                                    async with persist_sess.begin():
                                        msg = Message(
                                            conversation_id=ctx.conv_id,
                                            role="ai",
                                            content=str(
                                                getattr(last_ai_msg, "content", "")
                                            ),
                                            tool_calls=tool_calls,
                                            parent_id=persisted_parent_id,
                                        )
                                        persist_sess.add(msg)
                                        await persist_sess.flush()
                                        persisted_parent_id = msg.id
                                persisted_tool_batches.add(sig)
                        if "tools" in chunk:
                            for tm in chunk["tools"]["messages"]:
                                if (
                                    isinstance(tm, ToolMessage)
                                    and tm.name
                                    and tm.name not in tools_used
                                ):
                                    tools_used.append(tm.name)
                                if isinstance(tm, ToolMessage):
                                    tid = str(
                                        getattr(tm, "tool_call_id", None)
                                        or uuid.uuid4()
                                    )
                                    if tid in persisted_tool_results:
                                        continue
                                    async with AsyncSessionLocal() as persist_sess:
                                        async with persist_sess.begin():
                                            tmsg = Message(
                                                conversation_id=ctx.conv_id,
                                                role="tool",
                                                content=serialize_tool_message(tm),
                                                parent_id=persisted_parent_id,
                                            )
                                            persist_sess.add(tmsg)
                                            await persist_sess.flush()
                                            persisted_parent_id = tmsg.id
                                    persisted_tool_results.add(tid)
                        events, full_content = sse_events_from_chunk(
                            chunk, full_content, ctx.human_msg_id
                        )
                        for event_str in events:
                            yield event_str
                        if await is_disconnected_func():
                            return
            stream_completed = True
        except Exception:
            stream_error = True
            logger.exception("chat_stream_service_error")
            yield {"type": "error", "content": "Internal server error during streaming"}
        finally:
            await self._finalize_stream(
                ctx=ctx,
                llm=llm,
                full_content=full_content,
                last_ai_msg=last_ai_msg,
                persisted_parent_id=persisted_parent_id,
                stream_completed=stream_completed,
                stream_error=stream_error,
                agent_session_id=agent_session_id,
                tools_used=tools_used,
                compressed_summary=compressed_summary,
            )

    async def _finalize_stream(
        self,
        ctx: ChatContext,
        llm: ResolvedLLMConfig,
        full_content: str,
        last_ai_msg: Any,
        persisted_parent_id: uuid.UUID | None,
        stream_completed: bool,
        stream_error: bool,
        agent_session_id: uuid.UUID | None,
        tools_used: list[str],
        compressed_summary: str | None,
    ) -> None:
        """流式处理结束后的清理和持久化逻辑。"""
        new_title = None
        ai_msg_id = None
        tokens_in, tokens_out = extract_token_counts(last_ai_msg)

        if full_content:
            try:
                if stream_completed and ctx.is_first_exchange:
                    from app.agent.title_generator import generate_title

                    new_title = await generate_title(
                        user_message=ctx.user_content,
                        ai_reply=full_content,
                        provider=llm.provider,
                        model=llm.model_name,
                        api_key=llm.api_key,
                        base_url=llm.base_url,
                    )

                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        saved_ai = Message(
                            conversation_id=ctx.conv_id,
                            role="ai",
                            content=full_content,
                            model_provider=llm.provider,
                            model_name=llm.model_name,
                            tokens_input=tokens_in,
                            tokens_output=tokens_out,
                            parent_id=persisted_parent_id,
                        )
                        session.add(saved_ai)
                        await session.flush()
                        ai_msg_id = saved_ai.id
                        conv = await session.get(Conversation, ctx.conv_id)
                        if conv:
                            conv.active_leaf_id = ai_msg_id
                            if new_title:
                                conv.title = new_title

                asyncio.create_task(sync_conversation_to_markdown(ctx.conv_id))
            except Exception:
                logger.exception("finalize_persistence_failed")

        if agent_session_id:
            try:
                status = "error" if stream_error else "completed"
                async with AsyncSessionLocal() as sess:
                    async with sess.begin():
                        await sess.execute(
                            update(AgentSession)
                            .where(AgentSession.id == agent_session_id)
                            .values(
                                status=status,
                                completed_at=datetime.now(UTC),
                                metadata_json={
                                    "model": llm.model_name,
                                    "provider": llm.provider,
                                    "tools_used": tools_used,
                                    "input_tokens": tokens_in or 0,
                                    "output_tokens": tokens_out or 0,
                                    "trigger_type": "chat",
                                },
                                context_summary=compressed_summary,
                            )
                        )
            except Exception:
                logger.warning("agent_session_update_failed")
