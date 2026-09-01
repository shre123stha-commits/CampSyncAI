from models.timetable import Lecture
from scheduler.study_slots import (
    day_sort_key,
    extract_study_slots,
    group_by_day,
    to_minutes,
    to_time,
)


def lec(day, start, end, subject="Subject"):
    return Lecture(day=day, start_time=start, end_time=end, subject=subject)


# ---------------- helpers ----------------


def test_to_minutes():
    assert to_minutes("00:00") == 0
    assert to_minutes("09:30") == 570
    assert to_minutes("23:59") == 1439


def test_to_time_roundtrip():
    for value in ("00:00", "08:15", "16:45", "22:00"):
        assert to_time(to_minutes(value)) == value


def test_day_sort_key_orders_the_week():
    days = ["Friday", "Monday", "Wednesday"]
    assert sorted(days, key=day_sort_key) == ["Monday", "Wednesday", "Friday"]


def test_group_by_day_sorts_within_day():
    lectures = [lec("Monday", "14:00", "15:00"), lec("Monday", "09:00", "10:00")]
    grouped = group_by_day(lectures)
    assert [x.start_time for x in grouped["Monday"]] == ["09:00", "14:00"]


# ---------------- core behaviour ----------------


def test_empty_input():
    assert extract_study_slots([]) == []


def test_single_lecture_yields_only_after_college():
    slots = extract_study_slots([lec("Monday", "09:00", "10:00")])
    assert len(slots) == 1
    assert slots[0].slot_type == "After College"
    assert slots[0].day == "Monday"


def test_gap_is_detected():
    slots = extract_study_slots(
        [lec("Monday", "09:00", "10:00"), lec("Monday", "11:00", "12:00")]
    )
    free = [s for s in slots if s.slot_type == "Free Period"]
    assert len(free) == 1
    assert (free[0].start_time, free[0].end_time) == ("10:00", "11:00")


def test_short_gap_is_ignored():
    slots = extract_study_slots(
        [lec("Monday", "09:00", "10:00"), lec("Monday", "10:15", "11:00")]
    )
    assert not [s for s in slots if s.slot_type == "Free Period"]


def test_exactly_30_minute_gap_is_kept():
    slots = extract_study_slots(
        [lec("Monday", "09:00", "10:00"), lec("Monday", "10:30", "11:00")]
    )
    assert len([s for s in slots if s.slot_type == "Free Period"]) == 1


def test_back_to_back_lectures_produce_no_gap():
    slots = extract_study_slots(
        [lec("Monday", "09:00", "10:00"), lec("Monday", "10:00", "11:00")]
    )
    assert not [s for s in slots if s.slot_type == "Free Period"]


# ---------------- the day-blindness regression ----------------


def test_no_phantom_gap_across_days():
    """The old implementation created a slot from Monday 17:00 to Tuesday 09:00."""
    lectures = [lec("Monday", "15:00", "17:00"), lec("Tuesday", "09:00", "10:00")]

    free = [s for s in extract_study_slots(lectures) if s.slot_type == "Free Period"]

    assert free == [], "A free period must never span two different days"


def test_after_college_slot_per_day():
    lectures = [
        lec("Monday", "09:00", "10:00"),
        lec("Tuesday", "09:00", "10:00"),
        lec("Wednesday", "09:00", "10:00"),
    ]

    after = [
        s for s in extract_study_slots(lectures) if s.slot_type == "After College"
    ]

    assert len(after) == 3
    assert {s.day for s in after} == {"Monday", "Tuesday", "Wednesday"}


def test_after_college_starts_after_a_late_lecture():
    slots = extract_study_slots([lec("Monday", "16:00", "18:00")])
    after = [s for s in slots if s.slot_type == "After College"][0]
    assert after.start_time == "18:00"


def test_after_college_respects_college_end_when_classes_finish_early():
    slots = extract_study_slots([lec("Monday", "09:00", "10:00")])
    after = [s for s in slots if s.slot_type == "After College"][0]
    assert after.start_time == "16:00"
    assert after.end_time == "22:00"


def test_slots_are_ordered_monday_first():
    lectures = [lec("Friday", "09:00", "10:00"), lec("Monday", "09:00", "10:00")]
    slots = extract_study_slots(lectures)
    assert slots[0].day == "Monday"


def test_no_after_college_slot_when_day_runs_late():
    slots = extract_study_slots(
        [lec("Monday", "20:00", "21:45")], study_day_end="22:00"
    )
    assert not [s for s in slots if s.slot_type == "After College"]
