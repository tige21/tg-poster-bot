import pytest
from scheduler.task_runner import parse_schedule, build_trigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger


def test_parse_daily():
    trigger = build_trigger("daily", "14:30")
    assert isinstance(trigger, CronTrigger)


def test_parse_interval():
    trigger = build_trigger("interval", "30")
    assert isinstance(trigger, IntervalTrigger)


def test_parse_once():
    trigger = build_trigger("once", "2026-06-01T10:00")
    assert isinstance(trigger, DateTrigger)


def test_parse_invalid():
    with pytest.raises(ValueError):
        build_trigger("unknown", "x")
