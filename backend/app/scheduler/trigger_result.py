# backend/app/scheduler/trigger_result.py
from dataclasses import dataclass, field


@dataclass
class TriggerResult:
    """Result of trigger evaluation.

    Reasons: fired, skipped, content_hash_unchanged, no_new_emails,
    llm_parse_error, error.
    """

    fired: bool
    reason: str
    trigger_ctx: dict | None = field(default=None)
