from state import PlannerState


def formatter_agent(state: PlannerState) -> PlannerState:

    print("\n========== Final Study Plan ==========\n")

    for task in state["study_plan"].tasks:
        print(f"Slot   : {task.slot}")
        print(f"Task   : {task.title}")
        print(f"Subject: {task.subject}")
        print(f"Reason : {task.reason}")
        print("-" * 40)

    return state