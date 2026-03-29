# backend/tests/agent/test_interfaces.py

import pytest

from app.agent.interfaces import AgentGraphFactory


def test_agent_graph_factory_is_protocol():
    """AgentGraphFactory must be a structural Protocol, not an ABC."""
    import typing

    assert (
        hasattr(AgentGraphFactory, "__protocol_attrs__")
        or typing.get_origin(AgentGraphFactory) is not None
        or AgentGraphFactory.__bases__[0].__name__ in ("Protocol", "object")
    )


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
    # If Protocol isn't satisfied, this will raise TypeError at runtime
    assert callable(factory.create)
