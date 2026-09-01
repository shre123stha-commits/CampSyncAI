"""Data access. All SQL lives here, so the agents and API stay clean."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlmodel import Session, select

from config import get_logger
from db.models import PlanRecord, SourceType, Student, TaskRecord
from db.security import hash_password, verify_password
from models.task import Task

logger = get_logger(__name__)


class DuplicateStudentError(ValueError):
    """A student with this registration number already exists."""


def task_fingerprint(subject: str, work: str, deadline: str) -> str:
    """A stable identity for a task across re-extractions.

    Completion state is keyed on this, so re-reading a document does not
    resurrect a task the student already ticked off. Deliberately excludes
    `days_remaining`, which changes daily.
    """
    raw = f"{subject.strip().lower()}|{work.strip().lower()}|{deadline.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------
# Students
# --------------------------------------------------------------------------


def get_student(session: Session, registration_no: str) -> Student | None:
    return session.exec(
        select(Student).where(Student.registration_no == registration_no)
    ).first()


def create_student(
    session: Session,
    registration_no: str,
    password: str,
    name: str = "",
) -> Student:
    if get_student(session, registration_no) is not None:
        raise DuplicateStudentError(
            f"An account for '{registration_no}' already exists."
        )

    student = Student(
        registration_no=registration_no,
        name=name,
        password_hash=hash_password(password),
    )

    session.add(student)
    session.commit()
    session.refresh(student)

    logger.info("Created account for %s", registration_no)

    return student


def authenticate(
    session: Session, registration_no: str, password: str
) -> Student | None:
    """Return the student on success, None on any failure."""
    student = get_student(session, registration_no)

    if student is None:
        # Hash anyway so a missing account and a wrong password take a
        # similar amount of time.
        verify_password(password, "$2b$12$" + "x" * 53)
        return None

    if not verify_password(password, student.password_hash):
        return None

    student.last_login = datetime.utcnow()
    session.add(student)
    session.commit()

    return student


# --------------------------------------------------------------------------
# Tasks
# --------------------------------------------------------------------------


def sync_tasks(
    session: Session,
    student_id: int,
    tasks: list[Task],
    source: SourceType = SourceType.DOCUMENT,
) -> list[TaskRecord]:
    """Upsert *tasks*, preserving completion state.

    Existing rows are matched by fingerprint and left alone (so `completed`
    survives); genuinely new tasks are inserted.
    """
    existing = {
        record.fingerprint: record
        for record in session.exec(
            select(TaskRecord).where(TaskRecord.student_id == student_id)
        ).all()
    }

    records: list[TaskRecord] = []

    for task in tasks:
        fingerprint = task_fingerprint(task.subject, task.work, task.deadline)

        record = existing.get(fingerprint)

        if record is None:
            record = TaskRecord(
                student_id=student_id,
                subject=task.subject,
                task_type=task.task_type,
                platform=task.platform,
                deadline=task.deadline,
                work=task.work,
                source=source,
                fingerprint=fingerprint,
            )
            session.add(record)

        records.append(record)

    session.commit()

    for record in records:
        session.refresh(record)

    logger.info(
        "Synced %d task(s) for student %d (%d new)",
        len(records),
        student_id,
        sum(1 for r in records if r.fingerprint not in existing),
    )

    return records


def list_tasks(
    session: Session, student_id: int, include_completed: bool = True
) -> list[TaskRecord]:
    statement = select(TaskRecord).where(TaskRecord.student_id == student_id)

    if not include_completed:
        statement = statement.where(TaskRecord.completed == False)  # noqa: E712

    return list(session.exec(statement).all())


def set_task_completed(
    session: Session, student_id: int, task_id: int, completed: bool
) -> TaskRecord | None:
    """Toggle completion. Scoped by student_id so one account cannot modify
    another's tasks."""
    record = session.exec(
        select(TaskRecord).where(
            TaskRecord.id == task_id, TaskRecord.student_id == student_id
        )
    ).first()

    if record is None:
        return None

    record.completed = completed
    record.completed_at = datetime.utcnow() if completed else None

    session.add(record)
    session.commit()
    session.refresh(record)

    return record


def completed_fingerprints(session: Session, student_id: int) -> set[str]:
    records = session.exec(
        select(TaskRecord).where(
            TaskRecord.student_id == student_id,
            TaskRecord.completed == True,  # noqa: E712
        )
    ).all()

    return {record.fingerprint for record in records}


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------


def save_plan(
    session: Session, student_id: int, mode: str, payload: dict
) -> PlanRecord:
    record = PlanRecord(
        student_id=student_id,
        mode=mode,
        payload=json.dumps(payload, default=str),
    )

    session.add(record)
    session.commit()
    session.refresh(record)

    return record


def latest_plan(
    session: Session, student_id: int, mode: str
) -> dict | None:
    record = session.exec(
        select(PlanRecord)
        .where(PlanRecord.student_id == student_id, PlanRecord.mode == mode)
        .order_by(PlanRecord.generated_at.desc())
    ).first()

    if record is None:
        return None

    try:
        return json.loads(record.payload)
    except json.JSONDecodeError:
        return None
