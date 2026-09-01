"""Read deadlines from an iCalendar (.ics) feed.

Almost every LMS — Moodle, Canvas, Blackboard, Google Calendar — exposes a
private iCal URL containing assignment due dates. The student pastes that URL
once; no password, no OAuth app registration, no IT approval.

This is the highest value-per-line integration available to the project.
"""

from __future__ import annotations

import re
from datetime import date, datetime

import requests
from icalendar import Calendar

from config import get_logger
from db.models import SourceType
from models.task import Task
from models.timetable import Lecture
from sources.base import BaseSource, SourceError

logger = get_logger(__name__)

FETCH_TIMEOUT = 20
MAX_FEED_BYTES = 5 * 1024 * 1024

# Query parameters that carry a private credential. Moodle uses `authtoken`,
# Canvas and Outlook embed opaque per-user keys in the path or query.
_SECRET_PARAMS = re.compile(
    r"((?:authtoken|token|key|secret|password|sig|signature)=)[^&\s\"']+",
    re.IGNORECASE,
)


def redact(text: str) -> str:
    """Mask credential-bearing query parameters in a URL or error string.

    Exception text from `requests` echoes the full URL, and an iCal URL is
    itself the secret. Anything shown to a student or written to a log must
    pass through here first.
    """
    return _SECRET_PARAMS.sub(r"\1***", text)

# Keywords used to infer a task type from the event title.
TYPE_KEYWORDS = (
    ("quiz", "Quiz"),
    ("exam", "Exam"),
    ("test", "Quiz"),
    ("lab", "Lab Report"),
    ("project", "Project"),
    ("presentation", "Presentation"),
    ("viva", "Viva"),
    ("tutorial", "Tutorial"),
    ("assignment", "Assignment"),
    ("submission", "Assignment"),
    ("homework", "Assignment"),
    ("due", "Assignment"),
)

# "Subject - Assignment 3 is due" -> subject "Subject"
SUBJECT_SPLIT = re.compile(r"\s+[-–—:]\s+|\s*[-–—:]\s+|\s*\(")


def normalise_url(url: str) -> str:
    """Accept the `webcal://` scheme browsers hand out."""
    url = url.strip()

    if url.lower().startswith("webcal://"):
        return "https://" + url[len("webcal://") :]

    return url


def validate_url(url: str) -> str:
    url = normalise_url(url)

    if not url:
        raise SourceError("Please provide a calendar URL.")

    if not url.lower().startswith(("http://", "https://")):
        raise SourceError("The calendar URL must start with http:// or https://.")

    return url


def infer_task_type(summary: str) -> str:
    """Match on whole words, so 'unlabelled' does not read as 'lab'."""
    lowered = summary.lower()

    for keyword, label in TYPE_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return label

    return "Assignment"


def infer_subject(summary: str) -> str:
    """Best-effort subject from an event title.

    Feeds vary wildly, so this stays deliberately simple: take the text before
    the first separator, and fall back to the whole title.
    """
    summary = summary.strip()

    if not summary:
        return "Untitled"

    parts = SUBJECT_SPLIT.split(summary, maxsplit=1)
    candidate = parts[0].strip(" -–—:()")

    return candidate or summary


def _to_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def parse_calendar(raw: bytes | str) -> list[Task]:
    """Convert an iCalendar document into Task objects."""
    try:
        calendar = Calendar.from_ical(raw)
    except Exception as exc:  # icalendar raises bare ValueError subclasses
        raise SourceError(
            "That does not look like a valid calendar feed."
        ) from exc

    tasks: list[Task] = []
    seen: set[tuple[str, str]] = set()

    for component in calendar.walk():
        if component.name not in {"VEVENT", "VTODO"}:
            continue

        summary = str(component.get("summary", "")).strip()

        if not summary:
            continue

        # VTODO uses DUE; VEVENT uses DTSTART.
        raw_due = component.get("due") or component.get("dtstart")

        if raw_due is None:
            continue

        due = _to_date(getattr(raw_due, "dt", None))

        if due is None:
            continue

        deadline = due.strftime("%d %B %Y")
        subject = infer_subject(summary)

        key = (subject.lower(), deadline)
        if key in seen:
            continue
        seen.add(key)

        description = str(component.get("description", "")).strip()

        tasks.append(
            Task(
                subject=subject,
                task_type=infer_task_type(summary),
                platform="Calendar",
                deadline=deadline,
                work=description or summary,
            )
        )

    logger.info("Parsed %d task(s) from calendar feed", len(tasks))

    return tasks


class ICSSource(BaseSource):
    """Fetches tasks from a student-supplied iCalendar URL."""

    source_type = SourceType.ICS
    label = "Calendar feed (.ics)"

    def fetch(self, config: dict) -> tuple[list[Lecture], list[Task]]:
        url = validate_url(config.get("url", ""))

        try:
            response = requests.get(
                url,
                timeout=FETCH_TIMEOUT,
                headers={"User-Agent": "CampusSyncAI/1.0"},
                stream=True,
            )
        except requests.exceptions.Timeout as exc:
            raise SourceError("The calendar feed timed out.") from exc
        except requests.exceptions.SSLError as exc:
            logger.warning("TLS failure for calendar feed: %s", redact(str(exc)))
            raise SourceError(
                "Could not verify the security certificate of the calendar "
                "server. Some university servers omit an intermediate "
                "certificate that browsers fetch automatically. Installing "
                "'truststore' (pip install truststore) lets CampusSync use "
                "your operating system's certificate store, which usually "
                "resolves this. Verification is never disabled."
            ) from exc
        except requests.exceptions.RequestException as exc:
            # The exception text echoes the full URL, which carries the
            # student's private authtoken. Never surface it verbatim.
            logger.warning("Calendar feed unreachable: %s", redact(str(exc)))
            raise SourceError(
                "Could not reach the calendar feed. Check the URL and that "
                "the server is reachable from this machine."
            ) from exc

        if response.status_code == 404:
            raise SourceError("The calendar feed was not found (404).")

        if response.status_code in {401, 403}:
            raise SourceError(
                "The calendar feed rejected the request. Check that the URL is "
                "the private/secret address from your LMS."
            )

        if response.status_code >= 400:
            raise SourceError(
                f"The calendar feed returned an error ({response.status_code})."
            )

        raw = response.raw.read(MAX_FEED_BYTES + 1, decode_content=True)

        if len(raw) > MAX_FEED_BYTES:
            raise SourceError("That calendar feed is too large to process.")

        if not raw.strip():
            raise SourceError("The calendar feed is empty.")

        return [], parse_calendar(raw)
