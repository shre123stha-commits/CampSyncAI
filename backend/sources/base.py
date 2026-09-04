"""The contract every data source implements.

A source normalises some external platform into the shared `Task` and
`Lecture` models. The planner never learns where data came from, so adding a
platform never requires touching the scheduling or planning code.

Security note: no adapter ever accepts a university password. Each one uses
either a document the student gave us, a URL they pasted, or an OAuth /
revocable token flow.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from db.models import SourceType
from models.task import Task
from models.timetable import Lecture


class SourceError(Exception):
    """A user-presentable failure while fetching from a source."""


@runtime_checkable
class Source(Protocol):
    """A provider of academic tasks and/or lectures."""

    source_type: SourceType

    @property
    def name(self) -> str:
        """Human-readable label shown in the UI."""
        ...

    def fetch(self, config: dict) -> tuple[list[Lecture], list[Task]]:
        """Return (lectures, tasks) for one student.

        Args:
            config: Adapter-specific settings, e.g. the registration number
                for documents or the feed URL for ICS.

        Raises:
            SourceError: on any user-fixable failure (bad URL, expired token).
        """
        ...


class BaseSource:
    """Shared defaults. Adapters may subclass this instead of the Protocol."""

    source_type: SourceType = SourceType.DOCUMENT
    label: str = "Source"

    @property
    def name(self) -> str:
        return self.label

    def fetch(self, config: dict) -> tuple[list[Lecture], list[Task]]:
        raise NotImplementedError
