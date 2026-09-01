"""Task listing, completion tracking and document upload."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from agents.academic_agent import (
    StudentNotFoundError,
    compute_days_remaining,
    load_academic_data,
)
from api.deps import current_student
from config import MAX_UPLOAD_BYTES, UPLOAD_DIR, get_logger
from db.models import Student
from db.repository import list_tasks, set_task_completed, sync_tasks
from db.session import get_session
from scheduler.plan_validator import expected_priority
from utils.cache import cache_clear

logger = get_logger(__name__)

router = APIRouter(tags=["tasks"])

ALLOWED_UPLOAD_SUFFIXES = {".docx"}


class CompletionRequest(BaseModel):
    completed: bool = True


def _serialise(record) -> dict:
    days_remaining = compute_days_remaining(record.deadline)

    return {
        "id": record.id,
        "subject": record.subject,
        "task_type": record.task_type,
        "platform": record.platform,
        "deadline": record.deadline,
        "work": record.work,
        "days_remaining": days_remaining,
        "priority": expected_priority(days_remaining).value,
        "completed": record.completed,
        "source": record.source.value,
    }


@router.get("/tasks")
def get_tasks(
    include_completed: bool = True,
    student: Student = Depends(current_student),
    session: Session = Depends(get_session),
):
    """The signed-in student's tasks, synced from their documents.

    Completion state is preserved across re-extraction via a content
    fingerprint, so ticking a task off survives a refresh.
    """
    try:
        lectures, extracted = load_academic_data(student.registration_no)

    except StudentNotFoundError:
        # No documents yet - return whatever is already persisted.
        lectures, extracted = [], []

    if extracted:
        sync_tasks(session, student.id, extracted)

    records = list_tasks(
        session, student.id, include_completed=include_completed
    )

    payload = sorted(
        (_serialise(record) for record in records),
        key=lambda item: (item["completed"], item["days_remaining"]),
    )

    return {
        "registration_no": student.registration_no,
        "tasks": payload,
        "lectures": [lecture.model_dump() for lecture in lectures],
        "stats": {
            "total": len(payload),
            "completed": sum(1 for t in payload if t["completed"]),
            "pending": sum(1 for t in payload if not t["completed"]),
        },
    }


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: int,
    request: CompletionRequest,
    student: Student = Depends(current_student),
    session: Session = Depends(get_session),
):
    record = set_task_completed(
        session, student.id, task_id, request.completed
    )

    if record is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    return _serialise(record)


@router.post("/refresh")
def refresh(student: Student = Depends(current_student)):
    """Drop the cached extraction so documents are re-read next time."""
    removed = cache_clear("extraction")

    return {"cleared": removed}


@router.post("/upload")
async def upload_document(
    kind: str,
    file: UploadFile = File(...),
    student: Student = Depends(current_student),
):
    """Upload a timetable or LMS document for the signed-in student.

    This is the credential-free ingestion path: it works at any university
    and needs no integration approval.
    """
    if kind not in {"timetable", "lms"}:
        raise HTTPException(
            status_code=422, detail="kind must be 'timetable' or 'lms'."
        )

    filename = file.filename or ""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=422,
            detail=f"Only {', '.join(sorted(ALLOWED_UPLOAD_SUFFIXES))} files "
            "are supported.",
        )

    contents = await file.read()

    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large (maximum "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
        )

    if not contents:
        raise HTTPException(status_code=422, detail="The file is empty.")

    target_dir = UPLOAD_DIR / kind
    target_dir.mkdir(parents=True, exist_ok=True)

    target = target_dir / f"{student.registration_no}.docx"
    target.write_bytes(contents)

    # The document changed, so the cached extraction is stale.
    cache_clear("extraction")

    logger.info(
        "Uploaded %s document for %s (%d bytes)",
        kind,
        student.registration_no,
        len(contents),
    )

    return {"status": "uploaded", "kind": kind, "bytes": len(contents)}
