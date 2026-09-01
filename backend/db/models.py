"""Database tables.

SQLite via SQLModel: no server to run, a single file to back up, and the same
Pydantic types the rest of the app already uses.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.utcnow()


class SourceType(str, Enum):
    """Where a task came from.

    Every member has an adapter except UPLOAD, which is folded into
    DOCUMENT because an uploaded file is read from the same directory.
    """

    DOCUMENT = "document"
    UPLOAD = "upload"
    ICS = "ics"
    CLASSROOM = "classroom"
    TEAMS = "teams"
    MOODLE = "moodle"


class Student(SQLModel, table=True):
    """An application account.

    `password_hash` is a bcrypt hash of a password the student chose *for this
    app*. We never collect or store a university credential.
    """

    __tablename__ = "student"

    id: int | None = Field(default=None, primary_key=True)
    registration_no: str = Field(index=True, unique=True)
    name: str = ""
    password_hash: str

    # bcrypt hash of a one-time recovery code shown once at sign-up. There is
    # no email service in this deployment, so this is the only self-service
    # way back into an account. Hashed for the same reason the password is:
    # it is equivalent to a password.
    recovery_hash: str = ""
    recovery_used_at: datetime | None = None

    created_at: datetime = Field(default_factory=utcnow)
    last_login: datetime | None = None


class TaskRecord(SQLModel, table=True):
    """A persisted academic task, including its completion state."""

    __tablename__ = "task"

    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(index=True, foreign_key="student.id")

    subject: str
    task_type: str = ""
    platform: str = "LMS"
    deadline: str = ""
    work: str = ""

    source: SourceType = Field(default=SourceType.DOCUMENT)

    # Stable identity across re-extractions, so completion survives a refresh.
    fingerprint: str = Field(index=True)

    completed: bool = Field(default=False, index=True)
    completed_at: datetime | None = None

    created_at: datetime = Field(default_factory=utcnow)


class PlanRecord(SQLModel, table=True):
    """A generated plan, kept for history and offline demos."""

    __tablename__ = "study_plan"

    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(index=True, foreign_key="student.id")
    mode: str
    generated_at: datetime = Field(default_factory=utcnow)
    payload: str  # JSON-encoded StudyPlanResponse


class SourceConnection(SQLModel, table=True):
    """A student's link to an external data source.

    `secret` holds an encrypted payload (an OAuth refresh token, or a private
    feed URL). It is encrypted, never hashed, because we must replay it.
    A university password is never stored here or anywhere else.
    """

    __tablename__ = "source_connection"

    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(index=True, foreign_key="student.id")

    source_type: SourceType = Field(index=True)
    label: str = ""

    secret: str = ""

    connected_at: datetime = Field(default_factory=utcnow)
    last_synced: datetime | None = None
    last_error: str = ""
    active: bool = Field(default=True)


class AuthSession(SQLModel, table=True):
    """A logged-in session, persisted so a restart does not sign everyone out.

    Only a SHA-256 hash of the bearer token is stored. A database leak
    therefore does not hand the attacker usable session tokens, the same
    reasoning that applies to password hashes.
    """

    __tablename__ = "auth_session"

    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(index=True, foreign_key="student.id")

    token_hash: str = Field(index=True, unique=True)

    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime = Field(index=True)
