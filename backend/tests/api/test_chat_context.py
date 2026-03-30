# backend/tests/api/test_chat_context.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat.context import ChatContext, build_chat_context
from app.core.llm_config import ResolvedLLMConfig


def _make_llm(tools=None):
    return ResolvedLLMConfig(
        provider="deepseek",
        model_name="deepseek-chat",
        api_key="sk-test",
        api_keys=["sk-test"],
        enabled_tools=tools,
        persona_override=None,
        raw_keys={},
    )


@pytest.fixture
def fake_db():
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.mark.anyio
async def test_build_chat_context_returns_chat_context(fake_db):
    """build_chat_context() must return a ChatContext with lc_messages."""
    conv_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_conv = MagicMock()
    mock_conv.id = conv_id
    mock_conv.persona_id = None
    mock_conv.persona_override = None
    mock_conv.workflow_dsl = None
    mock_conv.active_leaf_id = None

    fake_db.scalar = AsyncMock(return_value=mock_conv)
    fake_db.scalars = AsyncMock(return_value=MagicMock(all=lambda: []))
    fake_db.commit = AsyncMock()
    fake_db.add = MagicMock()
    fake_db.refresh = AsyncMock()

    user = MagicMock()
    user.id = user_id

    from app.api.chat.schemas import ChatRequest

    request = ChatRequest(
        conversation_id=conv_id,
        content="hello",
        parent_message_id=None,
        workspace_id=None,
    )

    llm = _make_llm()

    with patch("app.api.chat.context.build_rag_context", AsyncMock(return_value=None)):
        with patch(
            "app.api.chat.context.build_memory_message", AsyncMock(return_value=None)
        ):
            ctx = await build_chat_context(request, user, fake_db, llm)

    assert isinstance(ctx, ChatContext)
    assert ctx.lc_messages  # non-empty
    assert any(isinstance(m, SystemMessage) for m in ctx.lc_messages)
    assert ctx.conv_id == conv_id
