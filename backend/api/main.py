"""CampusSync AI HTTP API."""

from __future__ import annotations

from contextlib import asynccontextmanager

import sys
from pathlib import Path

# Allow `uvicorn api.main:app` from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from agents.academic_agent import (  # noqa: E402
    StudentNotFoundError,
    load_academic_data,
)
from api import routes_auth, routes_sources, routes_tasks  # noqa: E402
from api.deps import current_student  # noqa: E402
from db.models import Student  # noqa: E402
from db.repository import completed_fingerprints, save_plan  # noqa: E402
from db.session import get_session, init_db  # noqa: E402
from config import LMS_DIR, TIMETABLE_DIR, configure_logging, get_logger  # noqa: E402
from graph import graph  # noqa: E402
from models.enums import PlanMode  # noqa: E402
from models.study_plan import StudyPlanResponse  # noqa: E402
from scheduler.plan_validator import expected_priority  # noqa: E402
from utils.cache import cache_clear  # noqa: E402
from utils.llm_json import LLMOutputError  # noqa: E402

from fastapi import Depends  # noqa: E402
from sqlmodel import Session  # noqa: E402

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="CampusSync AI API",
    version="0.2.0",
    description="AI-powered academic study planner.",
)



@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app.router.lifespan_context = lifespan

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanRequest(BaseModel):
    registration_no: str = Field(min_length=1, max_length=32)
    mode: PlanMode = PlanMode.DAY_WITHOUT_TIMINGS


@app.exception_handler(LLMOutputError)
async def _llm_error_handler(_request, exc: LLMOutputError):
    logger.error("LLM failure: %s", exc)
    message = str(exc)

    if "LLM service error" in message:
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "The AI service is unavailable. Make sure Ollama is "
                    "running, then try again."
                )
            },
        )

    return JSONResponse(
        status_code=502,
        content={
            "detail": (
                "Could not generate a valid study plan. Please try again."
            )
        },
    )


app.include_router(routes_auth.router)
app.include_router(routes_tasks.router)
app.include_router(routes_sources.router)


@app.get("/")
def home():
    return {"message": "CampusSync AI Backend Running", "version": "0.2.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/students")
def list_students():
    """Registration numbers we currently hold documents for."""
    known = set()

    for directory in (TIMETABLE_DIR, LMS_DIR):
        if directory.exists():
            known.update(p.stem for p in directory.glob("*.docx"))

    return {"students": sorted(known)}


@app.get("/students/{registration_no}/tasks")
def student_tasks(registration_no: str):
    """The student's tasks and timetable, with no planning step.

    Served from the extraction cache when warm, so the dashboard can render
    immediately instead of waiting on the planner.
    """
    try:
        lectures, tasks = load_academic_data(registration_no)

    except StudentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except LLMOutputError:
        raise

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error while loading tasks")
        raise HTTPException(
            status_code=500, detail="Could not load your academic data."
        ) from exc

    payload = []

    for task in sorted(tasks, key=lambda t: t.days_remaining):
        item = task.model_dump()
        item["priority"] = expected_priority(task.days_remaining).value
        payload.append(item)

    return {
        "registration_no": registration_no,
        "tasks": payload,
        "lectures": [lecture.model_dump() for lecture in lectures],
    }


@app.post("/students/{registration_no}/refresh")
def refresh_student(registration_no: str):
    """Drop the cached extraction so the next request re-reads the documents."""
    removed = cache_clear("extraction")

    logger.info("Cleared %d cache entry/entries", removed)

    return {"cleared": removed}


@app.post("/generate-plan", response_model=StudyPlanResponse)
def generate_plan(request: PlanRequest) -> StudyPlanResponse:
    """Legacy unauthenticated endpoint, kept for the sample data demo."""
    logger.info(
        "Generating plan: student=%s mode=%s",
        request.registration_no,
        request.mode.value,
    )

    initial_state = {
        "registration_no": request.registration_no,
        "mode": request.mode.value,
        "timetable": [],
        "assignments": [],
        "classroom_tasks": [],
        "study_plan": None,
    }

    try:
        result = graph.invoke(initial_state)

    except StudentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except LLMOutputError:
        raise

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error while generating plan")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating the plan.",
        ) from exc

    plan = result.get("study_plan")

    if plan is None:
        raise HTTPException(
            status_code=502, detail="The planner did not return a study plan."
        )

    return plan


class MyPlanRequest(BaseModel):
    mode: PlanMode = PlanMode.DAY_WITHOUT_TIMINGS


@app.post("/my/generate-plan", response_model=StudyPlanResponse)
def generate_my_plan(
    request: MyPlanRequest,
    student: Student = Depends(current_student),
    session: Session = Depends(get_session),
) -> StudyPlanResponse:
    """Generate a plan for the signed-in student.

    Tasks the student has already ticked off are excluded, so the plan
    adapts to real progress rather than re-scheduling finished work.
    """
    from db.repository import task_fingerprint

    logger.info(
        "Generating plan for %s (mode=%s)",
        student.registration_no,
        request.mode.value,
    )

    done = completed_fingerprints(session, student.id)

    initial_state = {
        "registration_no": student.registration_no,
        "mode": request.mode.value,
        "timetable": [],
        "assignments": [],
        "classroom_tasks": [],
        "study_plan": None,
        "exclude_fingerprints": done,
    }

    try:
        result = graph.invoke(initial_state)

    except StudentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except LLMOutputError:
        raise

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error while generating plan")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating the plan.",
        ) from exc

    plan = result.get("study_plan")

    if plan is None:
        raise HTTPException(
            status_code=502, detail="The planner did not return a study plan."
        )

    save_plan(session, student.id, request.mode.value, plan.model_dump())

    return plan
