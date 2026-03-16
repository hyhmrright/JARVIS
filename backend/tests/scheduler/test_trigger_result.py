# backend/tests/scheduler/test_trigger_result.py
from app.scheduler.trigger_result import TriggerResult


def test_trigger_result_fired():
    r = TriggerResult(fired=True, reason="fired", trigger_ctx={"url": "x"})
    assert r.fired is True
    assert r.reason == "fired"
    assert r.trigger_ctx == {"url": "x"}


def test_trigger_result_skipped_defaults():
    r = TriggerResult(fired=False, reason="content_hash_unchanged")
    assert r.fired is False
    assert r.trigger_ctx is None
