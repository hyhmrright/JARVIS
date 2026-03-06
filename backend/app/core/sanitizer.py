"""Input sanitization utilities for user-submitted text."""

from __future__ import annotations

import re

# Control characters except common whitespace (\t \n \r)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_user_input(text: str) -> str:
    """Strip dangerous control characters from user input.

    Preserves legitimate whitespace (tab, newline, carriage return).
    Does not alter message semantics or block any content.
    """
    return _CONTROL_CHAR_RE.sub("", text)
