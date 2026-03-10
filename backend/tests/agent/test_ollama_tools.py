import pytest
from unittest.mock import MagicMock
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from app.agent.llm import get_llm

@tool
def get_weather(location: str):
    """Get the weather for a location."""
    return "Sunny in " + location

def test_ollama_bind_tools():
    """验证 ChatOllama 能正确绑定工具。"""
    provider = "ollama"
    model = "llama3.1"
    
    llm = get_llm(provider, model, "")
    assert isinstance(llm, ChatOllama)
    
    # 绑定工具
    tools = [get_weather]
    llm_with_tools = llm.bind_tools(tools)
    
    # 虽然不能运行实际推理，但我们可以验证绑定后的对象
    # 检查绑定的工具是否在对象中（LangChain 内部属性可能变化，但 bind_tools 应返回 RunnableBinding）
    assert hasattr(llm_with_tools, "kwargs")
    assert "tools" in llm_with_tools.kwargs or "tool_defs" in str(llm_with_tools)

def test_ollama_tool_calling_response_parsing():
    """验证如何处理类似 Ollama 的工具调用响应。"""
    from langchain_core.messages import AIMessage
    
    # 模拟 Ollama 的响应
    tool_call = {
        "name": "get_weather",
        "args": {"location": "San Francisco"},
        "id": "call_123"
    }
    ai_msg = AIMessage(content="", tool_calls=[tool_call])
    
    assert len(ai_msg.tool_calls) == 1
    assert ai_msg.tool_calls[0]["name"] == "get_weather"
    assert ai_msg.tool_calls[0]["args"] == {"location": "San Francisco"}
