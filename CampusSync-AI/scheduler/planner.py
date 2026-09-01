from models.study_plan import PlannedTask
from models.study_plan import StudyPlan
from models.task import Task


def generate_plan(
    registration_no: str,
    mode: str,
    assignments: list[Task],
    classroom_tasks: list[Task],
    timetable: str,
) -> StudyPlan:

    all_tasks = []

    all_tasks.extend(assignments)

    all_tasks.extend(classroom_tasks)

    planned_tasks = []

    for task in all_tasks:

        planned_tasks.append(

            PlannedTask(

                title=task.title,

                subject=task.subject,

                slot="After College",

                reason="Task scheduled according to deadline."

            )
        )

    return StudyPlan(

        registration_no=registration_no,

        mode=mode,

        strategy="Default",

        tasks=planned_tasks,

    )