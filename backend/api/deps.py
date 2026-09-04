"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from db.models import Student
from db.security import resolve_session
from db.session import get_session


def current_student(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Student:
    """Resolve the caller from a `Authorization: Bearer <token>` header.

    Raises 401 when the token is missing, malformed, expired or unknown.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401, detail="Invalid authorization header."
        )

    student_id = resolve_session(token)

    if student_id is None:
        raise HTTPException(
            status_code=401, detail="Session expired. Please log in again."
        )

    student = session.get(Student, student_id)

    if student is None:
        raise HTTPException(status_code=401, detail="Account no longer exists.")

    return student
