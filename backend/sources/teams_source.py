"""Read assignment deadlines from Microsoft Teams / Microsoft 365.

Two routes exist, and the choice between them is forced by Microsoft's
consent model rather than by preference:

1. **Education assignments** (`EduAssignments.ReadBasic`). The direct route -
   it returns real Teams assignments with due dates. Every education
   permission, including the read-only ones, is flagged
   `AdminConsentRequired: Yes`, so a student cannot approve it. The
   university's Microsoft 365 administrator must grant it tenant-wide.

2. **Calendar** (`Calendars.Read`). Not admin-restricted by Microsoft's
   default, so an individual student can usually consent for themselves.
   Teams assignment due dates surface as class calendar events, so this
   recovers most of the value without an IT ticket.

The adapter requests both scopes and degrades: if the education call comes
back 403 it falls through to the calendar and reports what happened, rather
than failing the whole source. A student whose tenant has not approved the
app still gets their deadlines.

As with every adapter here, no Microsoft password is ever seen by this
application - the student authenticates on Microsoft's own page and we store
only a revocable refresh token, encrypted at rest.
"""

from __future__ import annotations

from datetime import datetime

import requests

from config import (
    MS_CLIENT_ID,
    MS_CLIENT_SECRET,
    MS_REDIRECT_URI,
    MS_SCOPES,
    MS_TENANT,
    get_logger,
)
from db.models import SourceType
from models.task import Task
from models.timetable import Lecture
from sources.base import BaseSource, SourceError

logger = get_logger(__name__)

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"

AUTH_ROOT = "https://login.microsoftonline.com"

FETCH_TIMEOUT = 30

# Guards against a runaway account with thousands of classes or events.
MAX_CLASSES = 40
MAX_ITEMS = 200


def authorization_url(state: str) -> str:
    """Where to send the student to sign in with Microsoft."""
    from urllib.parse import urlencode

    query = urlencode(
        {
            "client_id": MS_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": MS_REDIRECT_URI,
            "response_mode": "query",
            "scope": " ".join(MS_SCOPES),
            "state": state,
            # Without this Microsoft may skip the consent screen and never
            # issue a refresh token.
            "prompt": "consent",
        }
    )

    return f"{AUTH_ROOT}/{MS_TENANT}/oauth2/v2.0/authorize?{query}"


def _token_request(payload: dict) -> dict:
    url = f"{AUTH_ROOT}/{MS_TENANT}/oauth2/v2.0/token"

    try:
        response = requests.post(url, data=payload, timeout=FETCH_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        raise SourceError("Could not reach Microsoft to sign you in.") from exc

    if response.status_code >= 400:
        detail = ""
        try:
            body = response.json()
            detail = body.get("error_description") or body.get("error") or ""
        except ValueError:
            pass

        # The description is Microsoft's own and can run to several lines.
        first_line = detail.split("\r")[0].split("\n")[0][:200]

        raise SourceError(
            f"Microsoft rejected the sign-in. {first_line}".strip()
        )

    return response.json()


def exchange_code(code: str) -> str:
    """Swap an authorization code for a refresh token."""
    data = _token_request(
        {
            "client_id": MS_CLIENT_ID,
            "client_secret": MS_CLIENT_SECRET,
            "code": code,
            "redirect_uri": MS_REDIRECT_URI,
            "grant_type": "authorization_code",
            "scope": " ".join(MS_SCOPES),
        }
    )

    refresh_token = data.get("refresh_token")

    if not refresh_token:
        raise SourceError(
            "Microsoft did not return a refresh token. Revoke the app at "
            "https://myapplications.microsoft.com and connect again."
        )

    return refresh_token


def access_token_from(refresh_token: str) -> str:
    """Mint a short-lived access token from the stored refresh token."""
    data = _token_request(
        {
            "client_id": MS_CLIENT_ID,
            "client_secret": MS_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": " ".join(MS_SCOPES),
        }
    )

    token = data.get("access_token")

    if not token:
        raise SourceError("Microsoft did not return an access token.")

    return token


def _get(path: str, token: str, params: dict | None = None) -> dict:
    try:
        response = requests.get(
            f"{GRAPH_ROOT}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=FETCH_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        raise SourceError("Could not reach Microsoft Graph.") from exc

    if response.status_code in {401, 403}:
        raise PermissionDenied(path)

    if response.status_code >= 400:
        raise SourceError(
            f"Microsoft Graph returned {response.status_code} for {path}."
        )

    try:
        return response.json()
    except ValueError as exc:
        raise SourceError("Microsoft Graph returned an unreadable response.") from exc


class PermissionDenied(Exception):
    """Graph refused the call, almost always for want of admin consent."""

    def __init__(self, path: str):
        super().__init__(path)
        self.path = path


def _parse_due(value: str | None) -> str:
    """Graph returns ISO-8601 UTC. Normalise to the app's display format."""
    if not value:
        return ""

    cleaned = value.replace("Z", "+00:00")

    try:
        return datetime.fromisoformat(cleaned).strftime("%d %B %Y")
    except ValueError:
        logger.debug("Unparseable Graph date %r", value)
        return ""


def _infer_type(title: str) -> str:
    from sources.ics_source import infer_task_type

    return infer_task_type(title)


def fetch_education_assignments(token: str) -> list[Task]:
    """The direct route. Raises PermissionDenied without admin consent."""
    tasks: list[Task] = []

    classes = _get("/education/me/classes", token).get("value", [])

    for course in classes[:MAX_CLASSES]:
        course_id = course.get("id")
        subject = (course.get("displayName") or "Teams class").strip()

        if not course_id:
            continue

        assignments = _get(
            f"/education/classes/{course_id}/assignments", token
        ).get("value", [])

        for assignment in assignments[:MAX_ITEMS]:
            # Drafts are not visible to students yet.
            if assignment.get("status") == "draft":
                continue

            title = (assignment.get("displayName") or "Assignment").strip()

            tasks.append(
                Task(
                    subject=subject,
                    task_type=_infer_type(title),
                    platform="Teams",
                    deadline=_parse_due(
                        (assignment.get("dueDateTime") or {}).get("dateTime")
                        if isinstance(assignment.get("dueDateTime"), dict)
                        else assignment.get("dueDateTime")
                    ),
                    work=title,
                )
            )

    logger.info("Fetched %d Teams assignment(s)", len(tasks))

    return tasks


def fetch_calendar_deadlines(token: str) -> list[Task]:
    """Fallback route: assignment due dates appear as calendar events."""
    tasks: list[Task] = []

    events = _get(
        "/me/events",
        token,
        params={
            "$select": "subject,start,bodyPreview,categories",
            "$top": str(MAX_ITEMS),
            "$orderby": "start/dateTime",
        },
    ).get("value", [])

    for event in events:
        title = (event.get("subject") or "").strip()

        if not title:
            continue

        start = event.get("start") or {}

        tasks.append(
            Task(
                subject=title,
                task_type=_infer_type(title),
                platform="Teams",
                deadline=_parse_due(start.get("dateTime")),
                work=(event.get("bodyPreview") or title).strip()[:300],
            )
        )

    logger.info("Fetched %d Teams calendar item(s)", len(tasks))

    return tasks


class TeamsSource(BaseSource):
    """Microsoft Teams assignments, with a calendar fallback."""

    source_type = SourceType.TEAMS
    label = "Microsoft Teams"

    def fetch(self, config: dict) -> tuple[list[Lecture], list[Task]]:
        refresh_token = config.get("refresh_token", "")

        if not refresh_token:
            raise SourceError("Microsoft Teams is not connected.")

        token = access_token_from(refresh_token)

        try:
            return [], fetch_education_assignments(token)

        except PermissionDenied:
            # Expected whenever the university has not granted admin consent
            # for the education scopes. The calendar usually still works.
            logger.info(
                "Education assignments denied; falling back to the calendar"
            )

        try:
            return [], fetch_calendar_deadlines(token)

        except PermissionDenied as exc:
            raise SourceError(
                "Microsoft refused access to both your class assignments and "
                "your calendar. Your university's Microsoft 365 administrator "
                "needs to approve this app before it can read Teams "
                "assignments."
            ) from exc
