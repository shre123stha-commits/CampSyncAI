"""Deterministic checks applied to an LLM-generated plan.

The model proposes; Python disposes. Anything that can be verified with
arithmetic is verified here rather than trusted to the LLM. Violations are
returned as human-readable strings and fed back into the retry prompt.
"""

from __future__ import annotations

from models.enums import PlanMode, Priority
from models.free_slot import FreeSlot
from models.study_plan import PlannedItem
from scheduler.study_slots import to_minutes

# Maximum study minutes we are willing to schedule on a single day.
MAX_MINUTES_PER_DAY = 6 * 60


def expected_priority(days_remaining: int) -> Priority:
    """The priority band a task should fall into, per the planning rules."""
    if days_remaining <= 3:
        return Priority.HIGH
    if days_remaining <= 10:
        return Priority.MEDIUM
    return Priority.LOW


def _safe_minutes(value: str) -> int | None:
    try:
        return to_minutes(value)
    except (ValueError, AttributeError, IndexError):
        return None


def validate_plan(
    items: list[PlannedItem],
    mode: PlanMode,
    slots: list[FreeSlot],
) -> list[str]:
    """Return a list of rule violations. An empty list means the plan is good."""
    problems: list[str] = []

    if not items:
        return problems

    # ---------------- timing presence ----------------

    if not mode.includes_timings:
        for item in items:
            if item.start_time or item.end_time:
                problems.append(
                    f"Mode '{mode.value}' must not include timings, but "
                    f"'{item.subject}' has {item.start_time}-{item.end_time}."
                )
                break
    else:
        for item in items:
            if not item.start_time or not item.end_time:
                problems.append(
                    f"Mode '{mode.value}' requires timings, but "
                    f"'{item.subject}' is missing start_time or end_time."
                )
                break

    # ---------------- priority consistency ----------------

    for item in items:
        expected = expected_priority(item.days_remaining)
        if item.priority != expected:
            problems.append(
                f"'{item.subject}' has {item.days_remaining} days remaining, "
                f"so priority must be '{expected.value}', not "
                f"'{item.priority.value}'."
            )

    # ---------------- daily workload ----------------

    if mode.includes_timings:
        per_day: dict[str, int] = {}

        for item in items:
            start = _safe_minutes(item.start_time)
            end = _safe_minutes(item.end_time)

            if start is None or end is None:
                continue

            if end <= start:
                problems.append(
                    f"'{item.subject}' ends at or before it starts "
                    f"({item.start_time}-{item.end_time})."
                )
                continue

            per_day[item.day] = per_day.get(item.day, 0) + (end - start)

        for day, minutes in per_day.items():
            if minutes > MAX_MINUTES_PER_DAY:
                problems.append(
                    f"{day or 'A day'} is overloaded with "
                    f"{minutes // 60}h{minutes % 60:02d} of study "
                    f"(maximum {MAX_MINUTES_PER_DAY // 60}h). "
                    "Spread the work across other days."
                )

    # ---------------- sessions must fit inside real free slots ----------------

    if mode.includes_timings and slots:
        by_day: dict[str, list[FreeSlot]] = {}
        for slot in slots:
            by_day.setdefault(slot.day.strip().lower(), []).append(slot)

        for item in items:
            start = _safe_minutes(item.start_time)
            end = _safe_minutes(item.end_time)

            if start is None or end is None or end <= start:
                continue

            day_slots = by_day.get(item.day.strip().lower())

            if not day_slots:
                continue

            fits = any(
                _safe_minutes(slot.start_time) is not None
                and _safe_minutes(slot.end_time) is not None
                and start >= _safe_minutes(slot.start_time)
                and end <= _safe_minutes(slot.end_time)
                for slot in day_slots
            )

            if not fits:
                available = ", ".join(
                    f"{s.start_time}-{s.end_time}" for s in day_slots
                )
                problems.append(
                    f"'{item.subject}' is scheduled {item.day} "
                    f"{item.start_time}-{item.end_time}, which is outside the "
                    f"student's free slots ({available})."
                )

    return problems
