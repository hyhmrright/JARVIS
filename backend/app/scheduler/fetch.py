"""Content fetching helpers.

URL validation (SSRF protection) and header sanitization.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx
import trafilatura

_HEADER_BLOCKLIST = frozenset(
    {
        "host",
        "x-forwarded-for",
        "x-forwarded-host",
        "x-forwarded-proto",
        "x-real-ip",
        "x-original-url",
        "x-rewrite-url",
    }
)

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_fetch_url(url: str) -> None:
    """Raise ValueError if URL points to a private/loopback/link-local address or
    non-HTTP scheme."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme '{parsed.scheme}' not allowed; only http/https")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    try:
        resolved_ip = socket.getaddrinfo(hostname, None)[0][4][0]
        addr = ipaddress.ip_address(resolved_ip)
    except (socket.gaierror, ValueError) as exc:
        raise ValueError(f"Cannot resolve hostname '{hostname}': {exc}") from exc

    for network in _PRIVATE_NETWORKS:
        if addr in network:
            raise ValueError(
                f"URL resolves to blocked address {addr} in network {network}"
            )


def sanitize_http_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove hop-by-hop and routing headers that could be abused for SSRF."""
    return {k: v for k, v in headers.items() if k.lower() not in _HEADER_BLOCKLIST}


async def fetch_page_content(
    url: str,
    http_headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    max_chars: int = 8000,
) -> str:
    """
    Fetch URL and extract main text content via trafilatura.

    Raises ValueError if URL is blocked by SSRF policy.
    Returns empty string if extraction fails (safe fallback).
    """
    validate_fetch_url(url)
    safe_headers = sanitize_http_headers(http_headers or {})

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = await client.get(url, headers=safe_headers)
        response.raise_for_status()
        html = response.text

    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
    )
    text = extracted or ""
    return text[:max_chars]
