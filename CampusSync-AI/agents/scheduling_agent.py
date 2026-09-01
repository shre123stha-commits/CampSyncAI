from scheduler.planner import generate_plan
from state import PlannerState


def scheduling_agent(state: PlannerState) -> PlannerState:

    print("\n========== Scheduling Agent ==========")

    state["study_plan"] = generate_plan(
        registration_no=state["registration_no"],
        mode=state["mode"],
        assignments=state["assignments"],
        classroom_tasks=state["classroom_tasks"],
        timetable=state["timetable"],
    )

    print("Study plan generated.")

    return state