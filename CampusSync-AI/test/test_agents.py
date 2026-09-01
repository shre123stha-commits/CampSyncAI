from agents.academic_agent import academic_agent
from agents.classroom_agent import classroom_agent
from agents.scheduling_agent import scheduling_agent
from agents.formatter_agent import formatter_agent

state = {
    "registration_no": "24BAI1127",
    "mode": "day_with_timings",
    "timetable": "",
    "assignments": [],
    "classroom_tasks": [],
    "study_plan": None,
}

state = academic_agent(state)
state = classroom_agent(state)
state = scheduling_agent(state)
state = formatter_agent(state)