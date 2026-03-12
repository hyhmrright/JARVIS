"""Pydantic validation schemas for trigger metadata by trigger type."""

from pydantic import BaseModel, HttpUrl


class WebWatcherMetadata(BaseModel):
    url: HttpUrl
    last_hash: str | None = None


class SemanticWatcherMetadata(BaseModel):
    url: HttpUrl
    target: str
    fire_on_init: bool = False
    content_hash: str | None = None
    last_semantic_summary: str | None = None


class EmailWatcherMetadata(BaseModel):
    imap_host: str
    email_address: str
    imap_password: str | None = None
    imap_port: int = 993
    imap_folder: str = "INBOX"


_SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "web_watcher": WebWatcherMetadata,
    "semantic_watcher": SemanticWatcherMetadata,
    "email": EmailWatcherMetadata,
}


def validate_trigger_metadata(trigger_type: str, metadata: dict) -> BaseModel | None:
    """Validate metadata dict against the schema for trigger_type.

    Returns the validated model, or None for types with no schema.
    Raises ValidationError on invalid metadata.
    """
    schema = _SCHEMA_MAP.get(trigger_type)
    if schema is None:
        return None
    return schema(**metadata)
