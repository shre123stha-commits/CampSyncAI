from typing import Optional, TypedDict

from models.study_plan import StudyPlanResponse
from models.task import Task
from models.timetable import Lecture


class PlannerState(TypedDict, total=False):
    registration_no: str
    mode: str
    timetable: list[Lecture]
    assignments: list[Task]
    classroom_tasks: list[Task]
    study_plan: Optional[StudyPlanResponse]
