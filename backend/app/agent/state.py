from dataclasses import dataclass, field
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


@dataclass(kw_only=True)
class AgentState:
    messages: Annotated[list[BaseMessage], add_messages] = field(default_factory=list)
