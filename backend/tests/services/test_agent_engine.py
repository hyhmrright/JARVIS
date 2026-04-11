from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.db.models import Conversation, Message
from app.services.agent_engine import AgentEngine


@pytest.mark.anyio
async def test_run_blocking_integration_logic(db_session, client):
    """
    测试 AgentEngine 的 run_blocking 核心逻辑。

    采用半集成测试模式：Mock LLM 调用，但保留 DB 和领域模型的真实行为。
    这解决了 [Mock Abuse] 风险，确保数据库操作和叶子节点更新逻辑被真实验证。
    """
    # 1. 准备测试数据
    from tests.api.test_auth import create_test_user

    user = await create_test_user(db_session)
    content = "你好，JARVIS"

    # 2. 模拟 LLM Graph 的执行
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"messages": [AIMessage(content="你好！我是 JARVIS。")]}
    )

    # 3. 运行测试（Mock 外部依赖，保留核心业务编排逻辑）
    with (
        patch("app.services.agent_engine.create_graph", return_value=mock_graph),
        patch(
            "app.services.context_service.compact_messages",
            side_effect=lambda m, **k: m,
        ),
        patch(
            "app.services.config_service.ConfigService.get_llm_config",
            return_value=AsyncMock(),
        ),
    ):
        engine = AgentEngine(db_session)
        result = await engine.run_blocking(user.id, content)

    # 4. 验证行为
    assert result == "你好！我是 JARVIS。"

    # 验证数据库持久化 (Domain Model Logic)
    conv = await db_session.scalar(
        Conversation.__table__.select().where(Conversation.user_id == user.id)
    )
    assert conv is not None

    messages = (
        await db_session.execute(
            Message.__table__.select()
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at)
        )
    ).all()

    assert len(messages) == 2  # Human + AI
    assert messages[0].role == "human"
    assert messages[1].role == "ai"
    assert messages[1].content == "你好！我是 JARVIS。"

    # 验证叶子节点更新 (Domain logic in add_message)
    assert conv.active_leaf_id == messages[1].id


@pytest.mark.anyio
async def test_run_streaming_unhappy_path(db_session, client):
    """
    测试 AgentEngine 的 run_streaming 异常路径。
    验证在流式执行中发生内部错误时，能否正确产生 ErrorEvent，并且妥善结束事务。
    """
    from app.agent.protocol import ErrorEvent
    from tests.api.test_auth import create_test_user

    user = await create_test_user(db_session)
    content = "你好，流式测试"

    # 模拟内部抛出异常
    async def mock_classify_task(*args, **kwargs):
        raise ValueError("Simulated internal error")

    with (
        patch(
            "app.services.agent_engine.classify_task", side_effect=mock_classify_task
        ),
        patch(
            "app.services.context_service.compact_messages",
            side_effect=lambda m, **k: m,
        ),
        patch(
            "app.services.config_service.ConfigService.get_llm_config",
            return_value=AsyncMock(),
        ),
    ):
        engine = AgentEngine(db_session)
        events = []
        async for event in engine.run_streaming(user.id, content, conversation_id=None):
            events.append(event)

    # 验证是否收到了 ErrorEvent
    assert any(isinstance(e, ErrorEvent) for e in events)
    assert any(
        e.content == "Internal Engine Error"
        for e in events
        if isinstance(e, ErrorEvent)
    )
