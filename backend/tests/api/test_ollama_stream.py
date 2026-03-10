import pytest
from langchain_core.messages import AIMessage
from app.api.chat import _sse_events_from_chunk
import json

def test_sse_events_from_ollama_chunk():
    """验证 _sse_events_from_chunk 能正确处理类似 Ollama 的 AI 消息块。"""
    
    full_content = "Hello"
    # 模拟一个包含累积内容的块（这是 LangGraph 处理流的典型方式）
    ai_msg = AIMessage(content="Hello world")
    chunk = {"llm": {"messages": [ai_msg]}}
    
    events, updated_content = _sse_events_from_chunk(chunk, full_content)
    
    assert updated_content == "Hello world"
    assert len(events) == 1
    
    event_data = json.loads(events[0][6:]) # 去掉 "data: "
    assert event_data["type"] == "delta"
    assert event_data["delta"] == " world"
    assert event_data["content"] == "Hello world"

def test_sse_events_from_ollama_chunk_empty_delta():
    """验证当没有新内容时，不会生成 delta 事件。"""
    
    full_content = "Hello"
    ai_msg = AIMessage(content="Hello")
    chunk = {"llm": {"messages": [ai_msg]}}
    
    events, updated_content = _sse_events_from_chunk(chunk, full_content)
    
    assert updated_content == "Hello"
    assert len(events) == 0
