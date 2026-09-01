"""CampusSync AI HTTP API."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `uvicorn api.main:app` from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from agents.academic_agent import StudentNotFoundError  # noqa: E402
from config import LMS_DIR, TIMETABLE_DIR, configure_logging, get_logger  # noqa: E402
from graph import graph  # noqa: E402
from models.enums import PlanMode  # noqa: E402
from models.study_plan import StudyPlanResponse  # noqa: E402
from utils.llm_json import LLMOutputError  # noqa: E402

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="CampusSync AI API",
    version="0.2.0",
    description="AI-powered academic study planner.",
)

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


@app.post("/generate-plan", response_model=StudyPlanResponse)
def generate_plan(request: PlanRequest) -> StudyPlanResponse:
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
