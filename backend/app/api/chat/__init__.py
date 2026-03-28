"""Chat API package.

Re-exports ``router`` so that ``from app.api.chat import router`` continues
to work after the module was split into a package.
"""

from app.api.chat.routes import chat_regenerate, chat_stream, router

__all__ = ["router", "chat_stream", "chat_regenerate"]
