from datetime import datetime

from models.timetable import Lecture


COLLEGE_START = "08:00"
COLLEGE_END = "16:00"


def to_minutes(time_str: str) -> int:
    """Convert HH:MM to minutes."""
    hours, minutes = map(int, time_str.split(":"))
    return hours * 60 + minutes


def to_time(minutes: int) -> str:
    """Convert minutes back to HH:MM."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def find_free_slots(lectures: list[Lecture]):

    lectures = sorted(lectures, key=lambda x: x.start_time)

    free_slots = []

    current = to_minutes(COLLEGE_START)

    for lecture in lectures:

        lecture_start = to_minutes(lecture.start_time)

        lecture_end = to_minutes(lecture.end_time)

        if lecture_start > current:

            free_slots.append(
                {
                    "start": to_time(current),
                    "end": to_time(lecture_start)
                }
            )

        current = lecture_end

    if current < to_minutes(COLLEGE_END):

        free_slots.append(
            {
                "start": to_time(current),
                "end": COLLEGE_END
            }
        )

    return free_slots