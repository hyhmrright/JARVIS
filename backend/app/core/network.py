"""SSRF-safe DNS resolution utilities."""

import ipaddress
import socket
from functools import partial

import anyio


def _is_private_ip(addr: str) -> bool:
    try:
        return ipaddress.ip_address(addr).is_private
    except ValueError:
        return True  # unparseable → block


async def resolve_and_check_ip(hostname: str) -> bool:
    """Return True only if hostname resolves to a public routable IP."""
    try:
        results = await anyio.to_thread.run_sync(
            partial(socket.getaddrinfo, hostname, None)
        )
        for result in results:
            if _is_private_ip(str(result[4][0])):
                return False
        return True
    except Exception:
        return False
