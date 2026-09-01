from fastapi import FastAPI
from pydantic import BaseModel

from graph import graph

app = FastAPI(
    title="CampusSync AI API"
)


class PlanRequest(BaseModel):
    registration_no: str
    mode: str


@app.get("/")
def home():
    return {
        "message": "CampusSync AI Backend Running"
    }


@app.post("/generate-plan")
def generate_plan(request: PlanRequest):

    initial_state = {
        "registration_no": request.registration_no,
        "mode": request.mode,
        "timetable": [],
        "assignments": [],
        "classroom_tasks": [],
        "study_plan": None,
    }

    result = graph.invoke(initial_state)

    return result["study_plan"]