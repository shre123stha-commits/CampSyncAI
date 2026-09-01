from typing import TypedDict

from models.task import Task
from models.study_plan import StudyPlan
from models.timetable import Lecture


class PlannerState(TypedDict):

    registration_no: str

    mode: str

    timetable: list[Lecture]

    assignments: list[Task]

    classroom_tasks: list[Task]

    study_plan: StudyPlan