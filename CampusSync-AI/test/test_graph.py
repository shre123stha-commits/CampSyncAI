from graph import graph

initial_state = {
    "registration_no": "24BAI1127",
    "mode": "day_without_timings",
    "timetable": [],
    "assignments": [],
    "classroom_tasks": [],
    "study_plan": None,
}

result = graph.invoke(initial_state)

print("\n========== FINAL STATE ==========\n")

print(result)