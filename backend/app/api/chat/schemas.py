"""Pydantic request/response schemas for the chat API."""

import uuid

from pydantic import BaseModel, Field, field_validator


class FileContext(BaseModel):
    """会话中携带的文件上下文（文本已提取）。"""

    filename: str = Field(max_length=255)
    extracted_text: str = Field(max_length=30_000)


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    content: str = Field(min_length=1, max_length=50000)
    image_urls: list[str] | None = None
    workspace_id: uuid.UUID | None = None
    parent_message_id: uuid.UUID | None = None
    persona_id: uuid.UUID | None = None
    workflow_dsl: dict | None = None
    model_override: str | None = Field(None, max_length=100)
    file_context: FileContext | None = None

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if len(v) > 4:
            raise ValueError("Maximum 4 images per message")
        for url in v:
            if len(url) > 5_600_000:
                raise ValueError("Image too large (max 4 MB per image)")
        return v


class RegenerateRequest(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    workspace_id: uuid.UUID | None = None
    model_override: str | None = Field(None, max_length=100)
