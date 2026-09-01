"""Pydantic models describing the *actual* study-plan payload.

These replace the legacy `StudyPlan`/`PlannedTask` pair, which described an
older non-LLM code path that is no longer part of the graph.
"""

from pydantic import BaseModel, Field, field_validator

from models.enums import PlanMode, Priority


class PlannedItem(BaseModel):
    """A single scheduled piece of work in a generated plan."""

    day: str = ""
    start_time: str = ""
    end_time: str = ""
    subject: str
    task_type: str = ""
    work: str = ""
    deadline: str = ""
    priority: Priority = Priority.MEDIUM
    days_remaining: int = 0
    reason: str = ""

    @field_validator("priority", mode="before")
    @classmethod
    def _normalise_priority(cls, value):
        """Accept 'high', 'HIGH', ' High ' etc. from the model."""
        if isinstance(value, str):
            cleaned = value.strip().title()
            if cleaned in {p.value for p in Priority}:
                return cleaned
            return Priority.MEDIUM.value
        return value

    @field_validator("days_remaining", mode="before")
    @classmethod
    def _coerce_days(cls, value):
        """The model sometimes returns '5 days' or '' instead of an int."""
        if isinstance(value, str):
            digits = "".join(c for c in value if c.isdigit() or c == "-")
            return int(digits) if digits else 0
        if value is None:
            return 0
        return value

    @field_validator("start_time", "end_time", "day", "deadline", mode="before")
    @classmethod
    def _blank_none(cls, value):
        return "" if value is None else value


class StudyPlanResponse(BaseModel):
    """The response returned by POST /generate-plan."""

    mode: PlanMode
    registration_no: str = ""
    generated_on: str = ""
    plan: list[PlannedItem] = Field(default_factory=list)
