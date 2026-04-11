from dataclasses import dataclass, field
from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


@dataclass(kw_only=True)
class AgentState:
    """Agent 执行流程的状态模型。"""

    # 消息列表，使用 add_messages 模式进行增量合并
    messages: Annotated[list[BaseMessage], add_messages] = field(default_factory=list)

    # 递归深度，防止 subagent 无限循环
    depth: int = 0

    # 等待人工审批的工具调用信息
    pending_tool_call: dict[str, Any] | None = None

    # 人工审批结果
    approved: bool | None = None

    # 运行时元数据（如用户信息、会话 ID、已使用的工具列表等）
    metadata: dict[str, Any] = field(default_factory=dict)

    # 任务路由信息（如 "simple", "complex", "code" 等）
    route: str | None = None

    # 是否已完成任务（用于提前退出或特殊处理）
    is_completed: bool = False
