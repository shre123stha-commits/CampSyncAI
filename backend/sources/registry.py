"""Fan out over a student's connected sources and merge the results."""

from __future__ import annotations

from sqlmodel import Session

from config import get_logger
from db.crypto import try_decrypt
from db.models import SourceType
from db.repository import list_connections, record_sync
from models.task import Task
from sources.base import SourceError
from sources.classroom_source import ClassroomSource
from sources.ics_source import ICSSource

logger = get_logger(__name__)

# Adapters that are driven by a stored connection.
ADAPTERS = {
    SourceType.ICS: ICSSource(),
    SourceType.CLASSROOM: ClassroomSource(),
}


def _config_for(source_type: SourceType, secret: str) -> dict:
    if source_type is SourceType.ICS:
        return {"url": secret}
    if source_type is SourceType.CLASSROOM:
        return {"refresh_token": secret}
    return {}


def task_key(task: Task) -> tuple[str, str, str]:
    """Identity used to de-duplicate across sources."""
    return (
        task.subject.strip().lower(),
        task.work.strip().lower()[:80],
        task.deadline.strip().lower(),
    )


def merge_tasks(*groups: list[Task]) -> list[Task]:
    """Combine task lists, keeping the first occurrence of each task.

    Earlier groups win, so document/upload data takes precedence over a
    calendar feed describing the same deadline.
    """
    merged: list[Task] = []
    seen: set[tuple[str, str, str]] = set()

    for group in groups:
        for task in group:
            key = task_key(task)
            if key in seen:
                continue
            seen.add(key)
            merged.append(task)

    return merged


def fetch_connected_tasks(
    session: Session, student_id: int
) -> tuple[list[Task], list[str]]:
    """Fetch from every active connection.

    Returns (tasks, errors). A failing source never prevents the others from
    contributing - its message is collected and surfaced in the UI instead.
    """
    tasks: list[Task] = []
    errors: list[str] = []

    for connection in list_connections(session, student_id):
        adapter = ADAPTERS.get(connection.source_type)

        if adapter is None:
            continue

        secret = try_decrypt(connection.secret)

        if secret is None:
            message = f"{adapter.name}: stored credential is unreadable."
            errors.append(message)
            record_sync(session, connection, error=message)
            continue

        try:
            _, fetched = adapter.fetch(
                _config_for(connection.source_type, secret)
            )
            tasks.extend(fetched)
            record_sync(session, connection)

            logger.info(
                "Fetched %d task(s) from %s", len(fetched), adapter.name
            )

        except SourceError as exc:
            message = f"{adapter.name}: {exc}"
            errors.append(message)
            record_sync(session, connection, error=str(exc))
            logger.warning("Source failed: %s", message)

        except Exception as exc:  # noqa: BLE001 - never let one source break all
            message = f"{adapter.name}: unexpected error."
            errors.append(message)
            record_sync(session, connection, error=str(exc))
            logger.exception("Unexpected source failure")

    return tasks, errors
