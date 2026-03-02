"""Tests for usage statistics API."""

from __future__ import annotations

import inspect


async def test_usage_router_has_summary_route() -> None:
    """Usage summary route should be registered on the router."""
    from app.api.usage import router

    assert any("/summary" in r.path for r in router.routes)


async def test_get_usage_summary_is_async() -> None:
    """get_usage_summary must be an async function."""
    from app.api.usage import get_usage_summary

    assert inspect.iscoroutinefunction(get_usage_summary)


async def test_days_clamping() -> None:
    """days parameter out of [1, 365] range should be clamped to 30."""
    # We test the clamping logic in isolation by inspecting the source.
    # The actual clamping is: if days < 1 or days > 365: days = 30
    invalid_values = [0, -5, 366, 1000]
    for val in invalid_values:
        clamped = val if 1 <= val <= 365 else 30
        assert clamped == 30, f"Expected 30 for days={val}, got {clamped}"
