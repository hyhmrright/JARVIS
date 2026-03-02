"""Tests for the Live Canvas tool and event bus."""

import asyncio

from app.tools.canvas_tool import CanvasEventBus, create_canvas_tool


async def test_canvas_event_bus_publish_subscribe():
    """Events published to a conversation are received by subscribers."""
    bus = CanvasEventBus()
    received = []

    async def subscriber():
        async for event in bus.subscribe("conv-123"):
            received.append(event)
            break  # Stop after first event

    task = asyncio.create_task(subscriber())
    await asyncio.sleep(0.01)  # Let subscriber set up

    await bus.publish(
        "conv-123",
        {"type": "canvas_render", "html": "<h1>Test</h1>", "title": "Test"},
    )
    await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(received) == 1
    assert received[0]["type"] == "canvas_render"


async def test_canvas_event_bus_different_conversations():
    """Events are not shared between different conversations."""
    bus = CanvasEventBus()
    received_a = []
    received_b = []

    async def sub_a():
        async for event in bus.subscribe("conv-A"):
            received_a.append(event)
            break

    async def sub_b():
        async for event in bus.subscribe("conv-B"):
            received_b.append(event)
            break

    task_a = asyncio.create_task(sub_a())
    task_b = asyncio.create_task(sub_b())
    await asyncio.sleep(0.01)

    # Only publish to conv-A
    await bus.publish(
        "conv-A", {"type": "canvas_render", "html": "<p>A</p>", "title": "A"}
    )
    await asyncio.sleep(0.01)

    task_a.cancel()
    task_b.cancel()
    for t in [task_a, task_b]:
        try:
            await t
        except asyncio.CancelledError:
            pass

    assert len(received_a) == 1
    assert len(received_b) == 0  # conv-B got nothing


async def test_create_canvas_tool_returns_tool():
    """create_canvas_tool returns a properly named LangChain tool."""
    bus = CanvasEventBus()
    canvas_render = create_canvas_tool("conv-test", event_bus=bus)
    assert canvas_render.name == "canvas_render"
    desc = canvas_render.description.lower()
    assert "html" in desc or "canvas" in desc


async def test_canvas_render_tool_publishes_event():
    """Invoking canvas_render tool publishes an event to the bus."""
    bus = CanvasEventBus()
    received = []

    async def collector():
        async for event in bus.subscribe("test-conv"):
            received.append(event)
            break

    task = asyncio.create_task(collector())
    await asyncio.sleep(0.01)

    canvas_render = create_canvas_tool("test-conv", event_bus=bus)
    result = await canvas_render.ainvoke(
        {"html": "<h1>Hello</h1>", "title": "Greeting"}
    )
    await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert "rendered" in result.lower() or "canvas" in result.lower()
    assert len(received) == 1
    assert received[0]["html"] == "<h1>Hello</h1>"
    assert received[0]["title"] == "Greeting"
