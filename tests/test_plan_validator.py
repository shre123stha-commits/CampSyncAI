from models.enums import PlanMode, Priority
from models.free_slot import FreeSlot
from models.study_plan import PlannedItem
from scheduler.plan_validator import expected_priority, validate_plan


def item(**kwargs):
    base = dict(
        day="Monday",
        subject="Maths",
        work="Do the thing",
        days_remaining=5,
        priority="Medium",
    )
    base.update(kwargs)
    return PlannedItem(**base)


SLOTS = [
    FreeSlot(
        day="Monday",
        slot_type="After College",
        start_time="16:00",
        end_time="22:00",
    )
]


# ---------------- priority bands ----------------


def test_priority_bands():
    assert expected_priority(0) is Priority.HIGH
    assert expected_priority(3) is Priority.HIGH
    assert expected_priority(4) is Priority.MEDIUM
    assert expected_priority(10) is Priority.MEDIUM
    assert expected_priority(11) is Priority.LOW


def test_mismatched_priority_is_flagged():
    bad = item(days_remaining=1, priority="Low")
    problems = validate_plan([bad], PlanMode.DAY_WITHOUT_TIMINGS, [])
    assert any("must be 'High'" in p for p in problems)


# ---------------- timing presence ----------------


def test_untimed_mode_rejects_timings():
    bad = item(start_time="16:00", end_time="17:00")
    problems = validate_plan([bad], PlanMode.DAY_WITHOUT_TIMINGS, [])
    assert any("must not include timings" in p for p in problems)


def test_timed_mode_requires_timings():
    bad = item(start_time="", end_time="")
    problems = validate_plan([bad], PlanMode.DAY_WITH_TIMINGS, SLOTS)
    assert any("requires timings" in p for p in problems)


def test_valid_untimed_plan_passes():
    assert validate_plan([item()], PlanMode.DAY_WITHOUT_TIMINGS, []) == []


def test_valid_timed_plan_passes():
    good = item(start_time="16:00", end_time="17:30")
    assert validate_plan([good], PlanMode.DAY_WITH_TIMINGS, SLOTS) == []


# ---------------- time sanity ----------------


def test_end_before_start_is_flagged():
    bad = item(start_time="17:00", end_time="16:00")
    problems = validate_plan([bad], PlanMode.DAY_WITH_TIMINGS, SLOTS)
    assert any("ends at or before it starts" in p for p in problems)


def test_session_outside_free_slots_is_flagged():
    bad = item(start_time="09:00", end_time="10:00")
    problems = validate_plan([bad], PlanMode.DAY_WITH_TIMINGS, SLOTS)
    assert any("outside the student's free slots" in p for p in problems)


def test_overloaded_day_is_flagged():
    items = [
        item(subject="A", start_time="16:00", end_time="20:00"),
        item(subject="B", start_time="20:00", end_time="22:00"),
        item(subject="C", start_time="16:00", end_time="17:00"),
    ]
    problems = validate_plan(items, PlanMode.DAY_WITH_TIMINGS, SLOTS)
    assert any("overloaded" in p for p in problems)


def test_empty_plan_is_valid():
    assert validate_plan([], PlanMode.WEEK_WITH_TIMINGS, SLOTS) == []
