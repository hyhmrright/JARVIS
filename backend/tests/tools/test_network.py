"""Tests for SSRF-safe DNS resolver."""

from unittest.mock import patch

import pytest

from app.core.network import resolve_and_check_ip


@pytest.mark.anyio
async def test_private_ipv4_blocked():
    with patch(
        "socket.getaddrinfo",
        return_value=[(None, None, None, None, ("192.168.1.1", 0))],
    ):
        assert await resolve_and_check_ip("internal.local") is False


@pytest.mark.anyio
async def test_loopback_blocked():
    with patch(
        "socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 0))]
    ):
        assert await resolve_and_check_ip("localhost") is False


@pytest.mark.anyio
async def test_public_ip_allowed():
    with patch(
        "socket.getaddrinfo",
        return_value=[(None, None, None, None, ("93.184.216.34", 0))],
    ):
        assert await resolve_and_check_ip("example.com") is True


@pytest.mark.anyio
async def test_unresolvable_host_blocked():
    import socket

    with patch("socket.getaddrinfo", side_effect=socket.gaierror("no such host")):
        assert await resolve_and_check_ip("does-not-exist.invalid") is False


@pytest.mark.anyio
async def test_ipv6_loopback_blocked():
    with patch(
        "socket.getaddrinfo", return_value=[(None, None, None, None, ("::1", 0, 0, 0))]
    ):
        assert await resolve_and_check_ip("ip6-localhost") is False


@pytest.mark.anyio
async def test_link_local_blocked():
    with patch(
        "socket.getaddrinfo",
        return_value=[(None, None, None, None, ("169.254.169.254", 0))],
    ):
        assert await resolve_and_check_ip("metadata.internal") is False
