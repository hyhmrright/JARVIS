"""Unit tests for the rate-limit key function."""

import re
from unittest.mock import patch

from starlette.requests import Request

from app.core.limiter import _get_user_or_ip, get_trusted_client_ip


def _make_request(
    auth_header: str | None = None,
    ip: str = "1.2.3.4",
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if auth_header:
        headers.append((b"authorization", auth_header.encode()))
    if extra_headers:
        headers.extend(extra_headers)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": (ip, 1234),
        "query_string": b"",
    }
    return Request(scope)


def test_authenticated_user_key():
    req = _make_request(auth_header="Bearer valid.token.here")
    # Patch the source module: limiter.py imports decode_access_token lazily
    # inside the function, so the correct target is app.core.security
    # (not app.core.limiter which has no module-level binding for this name).
    with patch("app.core.security.decode_access_token", return_value="abc-123"):
        key = _get_user_or_ip(req)
    assert key == "user:abc-123"


def test_anonymous_falls_back_to_ip():
    req = _make_request()  # public IP "1.2.3.4"
    key = _get_user_or_ip(req)
    assert key == "1.2.3.4"


def test_invalid_token_falls_back_to_ip():
    req = _make_request(auth_header="Bearer bad.token")
    with patch(
        "app.core.security.decode_access_token", side_effect=Exception("invalid")
    ):
        key = _get_user_or_ip(req)
    assert key == "1.2.3.4"


def test_invalid_token_logs_debug_with_error_detail():
    """JWT decode failure must be logged at debug level with error= kwarg.

    FAILS before fix: exception swallowed silently (bare `except Exception: pass`).
    PASSES after fix: logger.debug("jwt_decode_failed_using_ip_fallback", error=...).
    """
    req = _make_request(auth_header="Bearer bad.token")
    with patch("app.core.security.decode_access_token", side_effect=ValueError("bad")):
        with patch("app.core.limiter.logger") as mock_logger:
            _get_user_or_ip(req)

    mock_logger.debug.assert_called_once()
    call_args = mock_logger.debug.call_args
    assert call_args.args[0] == "jwt_decode_failed_using_ip_fallback", (
        f"Expected event name 'jwt_decode_failed_using_ip_fallback', "
        f"got {call_args.args[0]!r}"
    )
    assert "error" in (call_args.kwargs or {}), (
        "logger.debug must include error= kwarg; "
        "exception details were silently discarded."
    )


def test_pat_token_uses_hash_key():
    """PAT tokens (jv_*) must produce a stable pat:<16-hex-char> key."""
    req = _make_request(auth_header="Bearer jv_sometoken")
    key = _get_user_or_ip(req)
    assert re.fullmatch(r"pat:[0-9a-f]{16}", key), (
        f"PAT key format must be 'pat:<16 hex chars>', got {key!r}"
    )


# --- get_trusted_client_ip tests ---


def test_trusted_real_ip_from_private_connection():
    """X-Real-IP is honoured when the direct TCP connection is from a private IP."""
    req = _make_request(
        ip="172.17.0.1",  # Docker bridge network — private
        extra_headers=[(b"x-real-ip", b"203.0.113.5")],
    )
    assert get_trusted_client_ip(req) == "203.0.113.5"


def test_x_real_ip_ignored_from_public_connection():
    """X-Real-IP is ignored when the direct TCP connection is from a public IP.

    This prevents audit-log IP spoofing by external clients.
    """
    req = _make_request(
        ip="1.2.3.4",  # public IP
        extra_headers=[(b"x-real-ip", b"5.6.7.8")],
    )
    assert get_trusted_client_ip(req) == "1.2.3.4"


def test_forwarded_for_used_from_private_connection():
    """X-Forwarded-For is used when direct IP is private and X-Real-IP is absent."""
    req = _make_request(
        ip="10.0.0.1",
        extra_headers=[(b"x-forwarded-for", b"198.51.100.1, 10.0.0.1")],
    )
    assert get_trusted_client_ip(req) == "198.51.100.1"


def test_forwarded_for_ignored_from_public_connection():
    """X-Forwarded-For is ignored when the direct TCP connection is from a public IP."""
    req = _make_request(
        ip="1.2.3.4",
        extra_headers=[(b"x-forwarded-for", b"9.9.9.9")],
    )
    assert get_trusted_client_ip(req) == "1.2.3.4"


def test_no_client_returns_none():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": None,
        "query_string": b"",
    }
    req = Request(scope)
    assert get_trusted_client_ip(req) is None


def test_loopback_ip_trusts_proxy_headers():
    """127.0.0.1 is treated as private (local dev with a locally-run proxy)."""
    req = _make_request(
        ip="127.0.0.1",
        extra_headers=[(b"x-real-ip", b"8.8.8.8")],
    )
    assert get_trusted_client_ip(req) == "8.8.8.8"


def test_no_client_returns_unknown_rate_limit_key():
    """_get_user_or_ip returns 'unknown' when request.client is None."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": None,
        "query_string": b"",
    }
    req = Request(scope)
    key = _get_user_or_ip(req)
    assert key == "unknown"
