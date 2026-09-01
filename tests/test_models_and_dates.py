from datetime import datetime

import pytest

from agents.academic_agent import (
    UNKNOWN_DEADLINE_DAYS,
    compute_days_remaining,
)
from models.enums import PlanMode, Priority
from models.study_plan import PlannedItem, StudyPlanResponse

TODAY = datetime(2026, 8, 1)


# ---------------- date arithmetic ----------------


@pytest.mark.parametrize(
    "deadline,expected",
    [
        ("12 August 2026", 11),
        ("1 August 2026", 0),
        ("31 July 2026", -1),
        ("2026-08-15", 14),
        ("15/08/2026", 14),
        ("15-08-2026", 14),
        ("12 Aug 2026", 11),
        ("August 12, 2026", 11),
    ],
)
def test_deadline_formats(deadline, expected):
    assert compute_days_remaining(deadline, TODAY) == expected


@pytest.mark.parametrize("bad", ["", "next Friday", "TBA", "sometime"])
def test_unparseable_deadline_sorts_last(bad):
    assert compute_days_remaining(bad, TODAY) == UNKNOWN_DEADLINE_DAYS


def test_whitespace_is_tolerated():
    assert compute_days_remaining("  12 August 2026  ", TODAY) == 11


# ---------------- model coercion ----------------


def test_priority_case_is_normalised():
    assert PlannedItem(subject="X", priority="high").priority is Priority.HIGH
    assert PlannedItem(subject="X", priority="  LOW ").priority is Priority.LOW


def test_unknown_priority_falls_back_to_medium():
    assert PlannedItem(subject="X", priority="urgent!").priority is Priority.MEDIUM


def test_days_remaining_from_string():
    assert PlannedItem(subject="X", days_remaining="5 days").days_remaining == 5
    assert PlannedItem(subject="X", days_remaining="").days_remaining == 0
    assert PlannedItem(subject="X", days_remaining=None).days_remaining == 0


def test_none_fields_become_empty_strings():
    parsed = PlannedItem(subject="X", start_time=None, day=None, deadline=None)
    assert parsed.start_time == ""
    assert parsed.day == ""
    assert parsed.deadline == ""


# ---------------- mode enum ----------------


def test_mode_properties():
    assert PlanMode.DAY_WITH_TIMINGS.includes_timings
    assert not PlanMode.DAY_WITHOUT_TIMINGS.includes_timings
    assert PlanMode.WEEK_WITH_TIMINGS.is_weekly
    assert not PlanMode.DAY_WITH_TIMINGS.is_weekly


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        PlanMode("monthly_plan")


def test_study_plan_response_defaults_to_empty():
    response = StudyPlanResponse(mode=PlanMode.DAY_WITH_TIMINGS)
    assert response.plan == []
