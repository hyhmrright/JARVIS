from langchain_core.messages import AIMessage

from app.agent.interpreter import events_from_chunk


def test_sse_events_from_ollama_chunk():
    """验证 events_from_chunk 能正确处理类似 Ollama 的 AI消息块。"""

    full_content = "Hello"
    # 模拟一个包含累积内容的块
    ai_msg = AIMessage(content="Hello world")
    chunk = {"llm": {"messages": [ai_msg]}}

    events, updated_content = events_from_chunk(chunk, full_content)

    assert updated_content == "Hello world"
    assert len(events) == 1
    assert events[0].type == "delta"
    assert events[0].delta == " world"


def test_sse_events_from_ollama_chunk_empty_delta():
    """验证当没有新内容时，不会生成 delta 事件。"""

    full_content = "Hello"
    ai_msg = AIMessage(content="Hello")
    chunk = {"llm": {"messages": [ai_msg]}}

    events, updated_content = events_from_chunk(chunk, full_content)

    assert updated_content == "Hello"
    assert len(events) == 0
