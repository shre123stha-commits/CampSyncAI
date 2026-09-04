"""Loads the student's timetable and LMS tasks from their documents."""

from __future__ import annotations

from datetime import datetime

from config import LMS_DIR, TIMETABLE_DIR, UPLOAD_DIR, get_logger
from extractors.task_extractor import extract_tasks
from extractors.timetable_extractor import extract_timetable
from models.task import Task
from models.timetable import Lecture
from utils.cache import cache_get, cache_set, fingerprint_files
from utils.doc_loader import read_docx

CACHE_NAMESPACE = "extraction"

logger = get_logger(__name__)

DEADLINE_FORMATS = (
    "%d %B %Y",
    "%d %b %Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
)

# Sentinel used when a deadline cannot be parsed, so the task sorts last
# instead of appearing urgent.
UNKNOWN_DEADLINE_DAYS = 999


class StudentNotFoundError(FileNotFoundError):
    """No documents exist for the given registration number."""


def compute_days_remaining(deadline: str, today: datetime | None = None) -> int:
    """Days between *today* and *deadline*, computed deterministically.

    The LLM is never trusted with this arithmetic.
    """
    if not deadline:
        return UNKNOWN_DEADLINE_DAYS

    reference = (today or datetime.today()).date()
    cleaned = deadline.strip()

    for fmt in DEADLINE_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
        return (parsed - reference).days

    logger.debug("Could not parse deadline %r", deadline)
    return UNKNOWN_DEADLINE_DAYS


def apply_days_remaining(tasks: list[Task]) -> list[Task]:
    for task in tasks:
        task.days_remaining = compute_days_remaining(task.deadline)
    return tasks


def _extract_documents(
    reg_no: str, timetable_path, lms_path
) -> tuple[list[Lecture], list[Task]]:
    """Run the two extraction LLM calls. Expensive; cached by the caller."""
    lectures: list[Lecture] = []

    if timetable_path.exists():
        lectures = extract_timetable(read_docx(timetable_path))
    else:
        logger.warning("No timetable document for %s", reg_no)

    tasks: list[Task] = []

    if lms_path.exists():
        tasks = extract_tasks(read_docx(lms_path), platform="LMS")
    else:
        logger.warning("No LMS document for %s", reg_no)

    return lectures, tasks


def resolve_document(kind: str, reg_no: str):
    """Locate a student's document, preferring their own upload.

    An uploaded file always wins over the bundled sample data, so a student
    who onboards themselves sees their own timetable.
    """
    uploaded = UPLOAD_DIR / kind / f"{reg_no}.docx"

    if uploaded.exists():
        return uploaded

    base = TIMETABLE_DIR if kind == "timetable" else LMS_DIR

    return base / f"{reg_no}.docx"


def load_academic_data(reg_no: str) -> tuple[list[Lecture], list[Task]]:
    """Return (lectures, tasks) for *reg_no*, using the disk cache when warm.

    The cache key includes a fingerprint of the source documents, so editing
    a document automatically invalidates the entry.

    `days_remaining` is deliberately recomputed *after* the cache lookup:
    it depends on today's date, so a cached value would go stale overnight.
    """
    timetable_path = resolve_document("timetable", reg_no)
    lms_path = resolve_document("lms", reg_no)

    if not timetable_path.exists() and not lms_path.exists():
        raise StudentNotFoundError(
            f"No academic documents found for registration number '{reg_no}'."
        )

    key = f"{reg_no}-{fingerprint_files(timetable_path, lms_path)}"

    cached = cache_get(CACHE_NAMESPACE, key)

    if cached is not None:
        lectures = [Lecture(**item) for item in cached.get("lectures", [])]
        tasks = [Task(**item) for item in cached.get("tasks", [])]
    else:
        lectures, tasks = _extract_documents(reg_no, timetable_path, lms_path)

        cache_set(
            CACHE_NAMESPACE,
            key,
            {
                "lectures": [item.model_dump() for item in lectures],
                "tasks": [item.model_dump() for item in tasks],
            },
        )

    # Date-dependent, so never cached.
    apply_days_remaining(tasks)

    return lectures, tasks


def academic_agent(state):
    """Read the student's documents and populate timetable + assignments."""
    reg_no = state["registration_no"]

    logger.info("Academic agent: loading documents for %s", reg_no)

    lectures, tasks = load_academic_data(reg_no)

    # Drop tasks the student has already completed, so plans reflect real
    # progress instead of re-scheduling finished work.
    excluded = state.get("exclude_fingerprints") or set()

    if excluded:
        from db.repository import task_fingerprint

        before = len(tasks)
        tasks = [
            task
            for task in tasks
            if task_fingerprint(task.subject, task.work, task.deadline)
            not in excluded
        ]
        logger.info(
            "Excluded %d completed task(s)", before - len(tasks)
        )

    state["timetable"] = lectures
    state["assignments"] = tasks

    logger.info(
        "Academic agent: %d lecture(s), %d task(s)", len(lectures), len(tasks)
    )

    return state
