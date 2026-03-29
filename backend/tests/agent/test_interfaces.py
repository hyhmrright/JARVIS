# backend/tests/agent/test_interfaces.py

import pytest

from app.agent.interfaces import AgentGraphFactory


def test_agent_graph_factory_is_runtime_checkable():
    """AgentGraphFactory must be @runtime_checkable so isinstance() works."""

    class ConcreteFactory:
        async def create(self, messages, config):
            return None

    class MissingCreate:
        pass

    # @runtime_checkable allows isinstance checks
    assert isinstance(ConcreteFactory(), AgentGraphFactory)
    assert not isinstance(MissingCreate(), AgentGraphFactory)


@pytest.mark.anyio
async def test_concrete_factory_satisfies_protocol():
    """Any async callable with the right signature satisfies AgentGraphFactory."""
    from unittest.mock import MagicMock

    from langgraph.graph.state import CompiledStateGraph

    class ConcreteFactory:
        async def create(self, messages, config):
            return MagicMock(spec=CompiledStateGraph)

    # Runtime check: Protocol is satisfied structurally
    factory = ConcreteFactory()
    assert callable(factory.create)
    assert isinstance(factory, AgentGraphFactory)
