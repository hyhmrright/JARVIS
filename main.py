"""使用 DeepSeek LLM 演示 LangGraph 基本用法的简单 Agent 图。"""

from typing import Annotated, Any, cast


from langchain_core.messages import AnyMessage, HumanMessage

from langchain_deepseek import ChatDeepSeek

from langgraph.graph import END, START, StateGraph

from langgraph.graph.message_state import add_messages

from typing_extensions import TypedDict


class AgentState(TypedDict):
    """定义 Agent 的状态架构。

    使用 Annotated 和 add_messages 确保消息可以正确合并。

    """

    messages: Annotated[list[AnyMessage], add_messages]


def call_deepseek(state: AgentState) -> dict[str, list[AnyMessage]]:
    """调用 DeepSeek 的真实 LLM 节点。

    参数:
        state: 包含消息历史的当前状态

    返回:
        包含 AI 响应的更新后状态
    """
    # 自动从系统环境变量 DEEPSEEK_API_KEY 读取密钥
    model = ChatDeepSeek(
        model="deepseek-chat",
    )
    response = model.invoke(state["messages"])
    return cast(
        AgentState,
        {"messages": [response]},
    )


def create_agent_graph() -> Any:
    """创建并配置 Agent 图。

    返回:
        编译后可执行的 StateGraph
    """
    # 使用显式定义的 AgentState 解决类型识别问题
    graph = StateGraph(AgentState)

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
    initial_state: AgentState = cast(
        AgentState, {"messages": [HumanMessage(content=prompt)]}
    )

    # 执行图
    result = graph.invoke(initial_state)

    # 打印结果
    print("Agent 执行结果:")
    for message in result["messages"]:
        message_type = type(message).__name__.replace("Message", "")
        print(f"{message_type.upper()}: {message.content}")


if __name__ == "__main__":
    main()
