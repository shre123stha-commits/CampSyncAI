"""Free-slot detection.

Slots are computed **per day**. The previous implementation sorted every
lecture in the week by start time alone, which produced phantom "free periods"
spanning from one day's last lecture to the next day's first, and attributed a
single after-college slot to the wrong day.
"""

from __future__ import annotations

from collections import defaultdict

from config import COLLEGE_END, MIN_STUDY_SLOT_MINUTES, STUDY_DAY_END
from models.free_slot import FreeSlot
from models.timetable import Lecture

# Canonical ordering so weekly plans read Monday -> Sunday.
DAY_ORDER = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def to_minutes(time_str: str) -> int:
    """Convert ``HH:MM`` to minutes since midnight."""
    hours, minutes = map(int, time_str.strip().split(":")[:2])
    return hours * 60 + minutes


def to_time(minutes: int) -> str:
    """Convert minutes since midnight back to ``HH:MM``."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def day_sort_key(day: str) -> tuple[int, str]:
    normalised = day.strip().lower()
    if normalised in DAY_ORDER:
        return (DAY_ORDER.index(normalised), normalised)
    return (len(DAY_ORDER), normalised)


def group_by_day(lectures: list[Lecture]) -> dict[str, list[Lecture]]:
    """Group lectures by day, each group sorted by start time."""
    grouped: dict[str, list[Lecture]] = defaultdict(list)

    for lecture in lectures:
        grouped[lecture.day].append(lecture)

    for day_lectures in grouped.values():
        day_lectures.sort(key=lambda lec: to_minutes(lec.start_time))

    return dict(grouped)


def extract_study_slots(
    lectures: list[Lecture],
    *,
    min_slot_minutes: int = MIN_STUDY_SLOT_MINUTES,
    college_end: str = COLLEGE_END,
    study_day_end: str = STUDY_DAY_END,
) -> list[FreeSlot]:
    """Return every usable study slot, grouped and ordered by day.

    For each day that has lectures we emit:

    * one ``Free Period`` per gap of at least *min_slot_minutes*, and
    * one ``After College`` slot running from the later of the day's last
      lecture and *college_end* until *study_day_end*.
    """
    if not lectures:
        return []

    slots: list[FreeSlot] = []
    grouped = group_by_day(lectures)

    for day in sorted(grouped, key=day_sort_key):
        day_lectures = grouped[day]

        # --- gaps between consecutive lectures on this day ---
        for current, nxt in zip(day_lectures, day_lectures[1:]):
            gap = to_minutes(nxt.start_time) - to_minutes(current.end_time)

            if gap >= min_slot_minutes:
                slots.append(
                    FreeSlot(
                        day=day,
                        slot_type="Free Period",
                        start_time=current.end_time,
                        end_time=nxt.start_time,
                    )
                )

        # --- after-college slot for this day ---
        last_end = max(to_minutes(lec.end_time) for lec in day_lectures)
        after_start = max(last_end, to_minutes(college_end))
        after_end = to_minutes(study_day_end)

        if after_end - after_start >= min_slot_minutes:
            slots.append(
                FreeSlot(
                    day=day,
                    slot_type="After College",
                    start_time=to_time(after_start),
                    end_time=to_time(after_end),
                )
            )

    return slots
