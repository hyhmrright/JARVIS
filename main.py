"""Simple agent graph demonstrating LangGraph usage with a mock LLM."""

from langgraph.graph import END, START, MessagesState, StateGraph


def mock_llm(state: MessagesState) -> MessagesState:
    """Mock LLM that returns a simple greeting.

    Args:
        state: Current state containing messages

    Returns:
        Updated state with AI response
    """
    return {"messages": [{"role": "ai", "content": "Hello! How can I help you today?"}]}


def create_agent_graph() -> StateGraph:
    """Create and configure the agent graph.

    Returns:
        Compiled StateGraph ready for execution
    """
    graph = StateGraph(MessagesState)

    # Add the mock LLM node
    graph.add_node("mock_llm", mock_llm)

    # Define the graph flow
    graph.add_edge(START, "mock_llm")
    graph.add_edge("mock_llm", END)

    return graph.compile()


def main() -> None:
    """Main entry point for the agent demonstration."""
    # Create and run the agent graph
    graph = create_agent_graph()

    # Initial user message
    initial_state: MessagesState = {"messages": [{"role": "user", "content": "Hello!"}]}

    # Execute the graph
    result = graph.invoke(initial_state)

    # Print the result
    print("Agent execution result:")
    for message in result["messages"]:
        print(f"{message['role'].upper()}: {message['content']}")


if __name__ == "__main__":
    main()
