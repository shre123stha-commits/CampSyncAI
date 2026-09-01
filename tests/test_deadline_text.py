"""Deadline phrasing, including the overdue case a real Moodle feed produces."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from frontend.components.deadline_text import format_days_remaining


def test_future_deadline_counts_down():
    assert format_days_remaining(4) == "⏳ 4d left"


def test_today_and_tomorrow_read_naturally():
    assert format_days_remaining(0) == "⏳ due today"
    assert format_days_remaining(1) == "⏳ due tomorrow"


def test_overdue_is_phrased_not_negated():
    """The bug: a passed deadline rendered as "-4d left"."""
    result = format_days_remaining(-4)

    assert "-4" not in result
    assert result == "⚠️ overdue by 4 days"


def test_overdue_by_one_day_is_singular():
    assert format_days_remaining(-1) == "⚠️ overdue by 1 day"


def test_unknown_deadline_sentinel_shows_nothing():
    """999 means 'could not parse', not 'due in 999 days'."""
    assert format_days_remaining(999) == ""
    assert format_days_remaining(1000) == ""


def test_missing_value_shows_nothing():
    assert format_days_remaining(None) == ""
    assert format_days_remaining("soon") == ""
