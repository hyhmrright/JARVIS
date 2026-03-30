"""Tests for the datetime tool."""

import re

import pytest

from app.tools.datetime_tool import get_datetime


@pytest.mark.anyio
async def test_get_datetime_returns_string():
    """get_datetime must return a non-empty string."""
    result = await get_datetime.ainvoke({})
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.anyio
async def test_get_datetime_includes_year():
    """Result must contain a 4-digit year."""
    result = await get_datetime.ainvoke({})
    assert re.search(r"\d{4}", result)


@pytest.mark.anyio
async def test_get_datetime_includes_utc():
    """Result must be labelled as UTC."""
    result = await get_datetime.ainvoke({})
    assert "UTC" in result


@pytest.mark.anyio
async def test_get_datetime_format():
    """Result must match the expected YYYY-MM-DD HH:MM:SS UTC format."""
    result = await get_datetime.ainvoke({})
    assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC", result)
