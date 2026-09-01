from models.timetable import Lecture
from models.task import Task
from models.free_slot import FreeSlot


def format_timetable(lectures: list[Lecture]) -> str:

    text = ""

    current_day = ""

    for lecture in lectures:

        if lecture.day != current_day:
            current_day = lecture.day
            text += f"\n{current_day}\n"

        text += (
            f"{lecture.start_time} - "
            f"{lecture.end_time} : "
            f"{lecture.subject}\n"
        )

    return text.strip()


def format_tasks(tasks):

    text = ""

    for i, task in enumerate(tasks, start=1):

        text += f"""
Task {i}

Subject:
{task.subject}

Task Type:
{task.task_type}

Deadline:
{task.deadline}

Days Remaining:
{task.days_remaining}

Work:
{task.work}

------------------------------------
"""

    return text


def format_slots(slots: list[FreeSlot]) -> str:

    text = ""

    current_day = ""

    for slot in slots:

        if slot.day != current_day:
            current_day = slot.day
            text += f"\n{current_day}\n"

        text += (
            f"{slot.start_time} - "
            f"{slot.end_time} "
            f"({slot.slot_type})\n"
        )

    return text.strip()