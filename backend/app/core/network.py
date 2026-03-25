"""SSRF-safe DNS resolution utilities."""

import ipaddress
import socket
from functools import partial

import anyio

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / AWS metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
        return any(ip in net for net in _BLOCKED_NETWORKS)
    except ValueError:
        return True  # unparseable → block


async def resolve_and_check_ip(hostname: str) -> bool:
    """Return True only if hostname resolves to a public routable IP.

    Performs DNS resolution in a thread pool to avoid blocking the event loop.
    Returns False for private/loopback/link-local IPs and on resolution errors.
    """
    try:
        results = await anyio.to_thread.run_sync(
            partial(socket.getaddrinfo, hostname, None)
        )
        for result in results:
            addr = str(result[4][0])
            if _is_private_ip(addr):
                return False
        return True
    except Exception:
        return False
