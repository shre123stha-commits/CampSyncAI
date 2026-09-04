"""Google Classroom via OAuth 2.0.

The student authenticates on Google's own consent screen and we receive a
scoped, revocable refresh token. We request read-only coursework scopes and
nothing else, so the token cannot be used to read mail or modify anything.

We never see the student's Google password — programmatic password sign-in is
both forbidden by Google's terms and technically blocked.
"""

from __future__ import annotations

from datetime import datetime

from config import (
    CLASSROOM_SCOPES,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    classroom_configured,
    get_logger,
)
from db.models import SourceType
from models.task import Task
from models.timetable import Lecture
from sources.base import BaseSource, SourceError

logger = get_logger(__name__)


def _client_config() -> dict:
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_REDIRECT_URI],
        }
    }


def build_flow(state: str | None = None):
    """Create an OAuth flow. Raises if the integration is not configured."""
    if not classroom_configured():
        raise SourceError(
            "Google Classroom is not configured on this server. Set "
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _client_config(), scopes=CLASSROOM_SCOPES, state=state
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI

    return flow


def authorization_url(state: str) -> str:
    """The URL to send the student to.

    `access_type=offline` + `prompt=consent` ensures Google returns a refresh
    token, which is what we persist.
    """
    flow = build_flow(state)

    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    return url


def exchange_code(code: str, state: str | None = None) -> str:
    """Swap an authorization code for a refresh token."""
    flow = build_flow(state)

    try:
        flow.fetch_token(code=code)
    except Exception as exc:  # noqa: BLE001 - many oauthlib error types
        raise SourceError(f"Google rejected the authorization: {exc}") from exc

    refresh_token = getattr(flow.credentials, "refresh_token", None)

    if not refresh_token:
        raise SourceError(
            "Google did not return a refresh token. Revoke the app's access "
            "in your Google account and connect again."
        )

    return refresh_token


def _credentials_from_refresh_token(refresh_token: str):
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=CLASSROOM_SCOPES,
    )


def _parse_due(coursework: dict) -> str:
    """Google returns dueDate as a {year, month, day} object."""
    due = coursework.get("dueDate")

    if not due:
        return ""

    try:
        return datetime(
            year=due["year"], month=due["month"], day=due["day"]
        ).strftime("%d %B %Y")
    except (KeyError, ValueError, TypeError):
        return ""


def coursework_to_tasks(courses: list[dict], coursework: dict) -> list[Task]:
    """Normalise Classroom coursework into the shared Task model.

    Args:
        courses: Course resources.
        coursework: Mapping of course id -> list of courseWork resources.
    """
    names = {course["id"]: course.get("name", "Course") for course in courses}

    tasks: list[Task] = []

    for course_id, items in coursework.items():
        subject = names.get(course_id, "Course")

        for item in items:
            # Skip anything already handed in or graded where state is known.
            if item.get("state") not in (None, "PUBLISHED"):
                continue

            work_type = item.get("workType", "ASSIGNMENT")
            type_label = {
                "ASSIGNMENT": "Assignment",
                "SHORT_ANSWER_QUESTION": "Quiz",
                "MULTIPLE_CHOICE_QUESTION": "Quiz",
            }.get(work_type, "Assignment")

            tasks.append(
                Task(
                    subject=subject,
                    task_type=type_label,
                    platform="Google Classroom",
                    deadline=_parse_due(item),
                    work=item.get("title", "") or item.get("description", ""),
                )
            )

    logger.info("Normalised %d Classroom task(s)", len(tasks))

    return tasks


class ClassroomSource(BaseSource):
    """Fetches coursework from Google Classroom."""

    source_type = SourceType.CLASSROOM
    label = "Google Classroom"

    def fetch(self, config: dict) -> tuple[list[Lecture], list[Task]]:
        refresh_token = config.get("refresh_token")

        if not refresh_token:
            raise SourceError("Google Classroom is not connected.")

        from googleapiclient.discovery import build

        try:
            credentials = _credentials_from_refresh_token(refresh_token)
            service = build(
                "classroom", "v1", credentials=credentials, cache_discovery=False
            )

            courses = (
                service.courses()
                .list(courseStates=["ACTIVE"], pageSize=50)
                .execute()
                .get("courses", [])
            )

            coursework: dict[str, list[dict]] = {}

            for course in courses:
                response = (
                    service.courses()
                    .courseWork()
                    .list(courseId=course["id"], pageSize=50)
                    .execute()
                )
                coursework[course["id"]] = response.get("courseWork", [])

        except Exception as exc:  # noqa: BLE001 - google client error variety
            raise SourceError(
                f"Could not read Google Classroom: {exc}"
            ) from exc

        return [], coursework_to_tasks(courses, coursework)
