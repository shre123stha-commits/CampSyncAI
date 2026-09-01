from agents.academic_agent import academic_agent
from scheduler.timetable import find_free_slots

state = {
    "registration_no": "24BAI1127",
    "mode": "day_with_timings",
    "timetable": [],
    "assignments": [],
    "classroom_tasks": [],
    "study_plan": None,
}

state = academic_agent(state)

slots = find_free_slots(state["timetable"])

print("\nFREE SLOTS\n")

for slot in slots:
    print(slot)