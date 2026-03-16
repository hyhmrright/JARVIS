import pytest
from pydantic import ValidationError

from app.scheduler.trigger_schemas import (
    EmailWatcherMetadata,
    SemanticWatcherMetadata,
    WebWatcherMetadata,
    validate_trigger_metadata,
)


def test_web_watcher_requires_url():
    with pytest.raises(ValidationError):
        WebWatcherMetadata(**{})


def test_web_watcher_valid():
    m = WebWatcherMetadata(url="https://example.com")
    assert str(m.url).startswith("https://")


def test_semantic_watcher_requires_url_and_target():
    with pytest.raises(ValidationError):
        SemanticWatcherMetadata(url="https://example.com")  # missing target
    with pytest.raises(ValidationError):
        SemanticWatcherMetadata(target="price")  # missing url


def test_email_watcher_requires_host_and_address():
    with pytest.raises(ValidationError):
        EmailWatcherMetadata(imap_host="imap.gmail.com")  # missing imap_user


def test_validate_trigger_metadata_unknown_type_passes():
    # cron type has no metadata requirements
    result = validate_trigger_metadata("cron", {})
    assert result is None  # returns None, no error


def test_validate_trigger_metadata_invalid_raises():
    with pytest.raises(ValidationError):
        validate_trigger_metadata("web_watcher", {})
