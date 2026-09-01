from models.free_slot import FreeSlot
from models.timetable import Lecture

COLLEGE_END = "16:00"


def to_minutes(time_str: str) -> int:
    hours, minutes = map(int, time_str.split(":"))
    return hours * 60 + minutes


def extract_study_slots(lectures: list[Lecture]) -> list[FreeSlot]:

    if not lectures:
        return []

    lectures = sorted(lectures, key=lambda x: x.start_time)

    slots = []

    MIN_STUDY_SLOT = 30  # Ignore anything less than 30 minutes

    for i in range(len(lectures) - 1):

        current = lectures[i]
        nxt = lectures[i + 1]

        gap = to_minutes(nxt.start_time) - to_minutes(current.end_time)

        if gap >= MIN_STUDY_SLOT:

            slots.append(
                FreeSlot(
                    day=current.day,
                    slot_type="Free Period",
                    start_time=current.end_time,
                    end_time=nxt.start_time,
                )
            )

    slots.append(
        FreeSlot(
            day=lectures[0].day,
            slot_type="After College",
            start_time=COLLEGE_END,
            end_time="22:00",
        )
    )

    return slots