"""Unit tests for the rate-limit key function."""

import re
from unittest.mock import patch

from starlette.requests import Request

from app.core.limiter import _get_user_or_ip


def _make_request(auth_header: str | None = None, ip: str = "1.2.3.4") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": ([(b"authorization", auth_header.encode())] if auth_header else []),
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


def test_anonymous_falls_back_to_ip(monkeypatch):
    req = _make_request()
    monkeypatch.setattr("app.core.limiter.get_remote_address", lambda r: "1.2.3.4")
    key = _get_user_or_ip(req)
    assert key == "1.2.3.4"


def test_invalid_token_falls_back_to_ip(monkeypatch):
    req = _make_request(auth_header="Bearer bad.token")
    monkeypatch.setattr("app.core.limiter.get_remote_address", lambda r: "1.2.3.4")
    with patch(
        "app.core.security.decode_access_token", side_effect=Exception("invalid")
    ):
        key = _get_user_or_ip(req)
    assert key == "1.2.3.4"


def test_invalid_token_logs_debug_with_error_detail(monkeypatch):
    """JWT decode failure must be logged at debug level with error= kwarg.

    FAILS before fix: exception swallowed silently (bare `except Exception: pass`).
    PASSES after fix: logger.debug("jwt_decode_failed_using_ip_fallback", error=...).
    """
    req = _make_request(auth_header="Bearer bad.token")
    monkeypatch.setattr("app.core.limiter.get_remote_address", lambda r: "1.2.3.4")
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
