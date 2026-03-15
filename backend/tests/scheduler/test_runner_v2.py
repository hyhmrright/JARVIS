import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.scheduler.runner import parse_trigger


def test_parse_trigger_interval_seconds():
    trigger = parse_trigger("@every 30s")
    assert isinstance(trigger, IntervalTrigger)
    assert trigger.interval.total_seconds() == 30


def test_parse_trigger_interval_minutes():
    trigger = parse_trigger("@every 5m")
    assert isinstance(trigger, IntervalTrigger)
    assert trigger.interval.total_seconds() == 300


def test_parse_trigger_interval_hours():
    trigger = parse_trigger("@every 2h")
    assert isinstance(trigger, IntervalTrigger)
    assert trigger.interval.total_seconds() == 7200


def test_parse_trigger_interval_days():
    trigger = parse_trigger("@every 1d")
    assert isinstance(trigger, IntervalTrigger)
    assert trigger.interval.total_seconds() == 86400


def test_parse_trigger_cron_fallback():
    trigger = parse_trigger("*/30 * * * *")
    assert isinstance(trigger, CronTrigger)


def test_parse_trigger_invalid_format():
    with pytest.raises(ValueError, match="Invalid interval format"):
        parse_trigger("@every 30x")
