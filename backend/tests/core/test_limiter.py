"""Unit tests for the rate-limit key function."""

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
