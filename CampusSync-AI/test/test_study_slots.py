from agents.academic_agent import academic_agent
from scheduler.study_slots import extract_study_slots

state = {
    "registration_no": "24BAI1127",
    "mode": "day_with_timings",
    "timetable": [],
    "assignments": [],
    "classroom_tasks": [],
    "study_plan": None,
}

state = academic_agent(state)

slots = extract_study_slots(state["timetable"])

print("\n====== STUDY SLOTS ======\n")

for slot in slots:
    print(slot)