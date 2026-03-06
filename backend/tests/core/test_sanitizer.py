"""Unit tests for sanitize_user_input."""

from app.core.sanitizer import sanitize_user_input


def test_normal_text_unchanged() -> None:
    assert sanitize_user_input("Hello, world!") == "Hello, world!"


def test_newlines_and_tabs_preserved() -> None:
    text = "line1\nline2\ttabbed\r\n"
    assert sanitize_user_input(text) == text


def test_null_bytes_removed() -> None:
    assert sanitize_user_input("hello\x00world") == "helloworld"


def test_control_chars_removed() -> None:
    # \x01-\x08, \x0b, \x0c, \x0e-\x1f are stripped
    assert sanitize_user_input("\x01\x07\x0b\x1f") == ""


def test_del_char_removed() -> None:
    assert sanitize_user_input("text\x7fmore") == "textmore"


def test_unicode_preserved() -> None:
    text = "你好 🌍 こんにちは"
    assert sanitize_user_input(text) == text


def test_empty_string() -> None:
    assert sanitize_user_input("") == ""


def test_mixed_content() -> None:
    result = sanitize_user_input("valid\x00text\nwith\x1bnewlines")
    assert result == "validtext\nwithnewlines"
    assert "\x00" not in result
    assert "\x1b" not in result
