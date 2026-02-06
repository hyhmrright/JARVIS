"""使用 DeepSeek LLM 演示 LangGraph 基本用法的简单 Agent 图。"""

from dataclasses import dataclass, field
from typing import Annotated, Any

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import END, START, StateGraph, add_messages


@dataclass(kw_only=True)
class AgentState:
    """使用 dataclass 定义 Agent 的状态架构。

    这是在 Python 3.13 中最稳健的类型定义方式，能够完美适配 DataclassLike 协议。
    """

    messages: Annotated[list[BaseMessage], add_messages] = field(default_factory=list)


def call_deepseek(state: AgentState) -> dict[str, Any]:
    """调用 DeepSeek 的真实 LLM 节点。

    参数:
        state: 包含消息历史的当前状态

    返回:
        要更新的状态字典
    """
    # 自动从系统环境变量 DEEPSEEK_API_KEY 读取密钥
    model = ChatDeepSeek(
        model="deepseek-chat",
    )
    # 调用模型，并获取响应
    response = model.invoke(state.messages)
    return {"messages": [response]}


def create_agent_graph() -> Any:
    """创建并配置 Agent 图。

    返回:
        编译后可执行的 StateGraph
    """
    # 显式使用 [AgentState] 泛型标注
    graph: StateGraph[AgentState] = StateGraph(AgentState)

    # 添加 DeepSeek LLM 节点
    graph.add_node("agent", call_deepseek)

    # 定义图的流程
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)

    return graph.compile()


def main() -> None:
    """Agent 演示的主入口函数。"""
    # 创建并运行 Agent 图
    graph = create_agent_graph()

    # 初始用户消息
    prompt = "你好，请自我介绍一下。"
    # 使用 dataclass 初始化状态
    initial_state = AgentState(messages=[HumanMessage(content=prompt)])

    # 执行图
    result = graph.invoke(initial_state)

    # 打印结果
    print("Agent 执行结果:")
    # 对于 dataclass 状态，LangGraph 返回的通常是该类的实例
    messages = result.messages if hasattr(result, "messages") else result["messages"]
    for message in messages:
        message_type = type(message).__name__.replace("Message", "")
        print(f"{message_type.upper()}: {message.content}")


if __name__ == "__main__":
    main()
