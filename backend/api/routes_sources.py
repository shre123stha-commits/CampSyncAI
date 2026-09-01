"""Connect and disconnect external data sources.

Every integration here uses OAuth or a revocable, student-supplied URL/token.
No endpoint accepts a university password.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session

from api.deps import current_student
from config import classroom_configured, get_logger
from db.crypto import encrypt
from db.models import SourceType, Student
from db.repository import (
    disconnect_source,
    get_connection,
    list_connections,
    upsert_connection,
)
from db.session import get_session
from sources.base import SourceError
from sources.classroom_source import authorization_url, exchange_code
from sources.ics_source import ICSSource, validate_url

logger = get_logger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])

# Short-lived OAuth state -> student id. Prevents CSRF on the callback.
_oauth_states: dict[str, int] = {}


class ICSConnectRequest(BaseModel):
    url: str
    label: str = ""


@router.get("")
def list_sources(
    student: Student = Depends(current_student),
    session: Session = Depends(get_session),
):
    """Every available source and whether this student has connected it."""
    connected = {
        connection.source_type: connection
        for connection in list_connections(session, student.id)
    }

    def describe(source_type: SourceType, name: str, available: bool, note: str):
        connection = connected.get(source_type)
        return {
            "type": source_type.value,
            "name": name,
            "available": available,
            "note": note,
            "connected": connection is not None,
            "label": connection.label if connection else "",
            "last_synced": (
                connection.last_synced.isoformat()
                if connection and connection.last_synced
                else None
            ),
            "last_error": connection.last_error if connection else "",
        }

    return {
        "sources": [
            describe(
                SourceType.DOCUMENT,
                "Uploaded documents",
                True,
                "Upload a .docx timetable or LMS export. No credentials needed.",
            ),
            describe(
                SourceType.ICS,
                "Calendar feed (.ics)",
                True,
                "Paste the private iCal URL from your LMS. Revocable, no password.",
            ),
            describe(
                SourceType.CLASSROOM,
                "Google Classroom",
                classroom_configured(),
                "Sign in with Google. Read-only coursework access, revocable.",
            ),
        ]
    }


# --------------------------------------------------------------------------
# ICS
# --------------------------------------------------------------------------


@router.post("/ics")
def connect_ics(
    request: ICSConnectRequest,
    student: Student = Depends(current_student),
    session: Session = Depends(get_session),
):
    """Validate and store a calendar feed URL (encrypted at rest)."""
    try:
        url = validate_url(request.url)

        # Fetch once so the student finds out immediately if it is wrong.
        _, tasks = ICSSource().fetch({"url": url})

    except SourceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    upsert_connection(
        session,
        student.id,
        SourceType.ICS,
        secret=encrypt(url),
        label=request.label or "Calendar feed",
    )

    return {"status": "connected", "tasks_found": len(tasks)}


# --------------------------------------------------------------------------
# Google Classroom
# --------------------------------------------------------------------------


@router.get("/classroom/authorize")
def classroom_authorize(student: Student = Depends(current_student)):
    """Return the Google consent URL for the student to visit."""
    if not classroom_configured():
        raise HTTPException(
            status_code=503,
            detail="Google Classroom is not configured on this server.",
        )

    state = secrets.token_urlsafe(24)
    _oauth_states[state] = student.id

    try:
        url = authorization_url(state)
    except SourceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"authorization_url": url}


@router.get("/classroom/callback", response_class=HTMLResponse)
def classroom_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    session: Session = Depends(get_session),
):
    """Google redirects the student's browser here after consent."""

    def page(title: str, message: str) -> HTMLResponse:
        return HTMLResponse(
            f"""<!doctype html><html><head><meta charset="utf-8">
            <title>{title}</title></head>
            <body style="font-family:system-ui;max-width:32rem;margin:4rem auto;
            text-align:center">
            <h2>{title}</h2><p>{message}</p>
            <p>You can close this tab and return to CampusSync AI.</p>
            </body></html>"""
        )

    if error:
        return page("Authorization cancelled", f"Google reported: {error}")

    student_id = _oauth_states.pop(state, None)

    if student_id is None:
        return page(
            "Invalid or expired request",
            "Please start the connection again from CampusSync AI.",
        )

    if not code:
        return page("Missing authorization code", "Please try again.")

    try:
        refresh_token = exchange_code(code, state)
    except SourceError as exc:
        return page("Could not connect", str(exc))

    upsert_connection(
        session,
        student_id,
        SourceType.CLASSROOM,
        secret=encrypt(refresh_token),
        label="Google Classroom",
    )

    return page(
        "Google Classroom connected",
        "Your coursework will now appear in CampusSync AI.",
    )


# --------------------------------------------------------------------------
# Disconnect
# --------------------------------------------------------------------------


@router.delete("/{source_type}")
def disconnect(
    source_type: SourceType,
    student: Student = Depends(current_student),
    session: Session = Depends(get_session),
):
    """Remove a connection and destroy its stored credential."""
    if not disconnect_source(session, student.id, source_type):
        raise HTTPException(status_code=404, detail="That source is not connected.")

    return {"status": "disconnected", "type": source_type.value}


@router.get("/status")
def status(
    student: Student = Depends(current_student),
    session: Session = Depends(get_session),
):
    return {
        "connected": [
            connection.source_type.value
            for connection in list_connections(session, student.id)
        ],
        "classroom_available": classroom_configured(),
    }
