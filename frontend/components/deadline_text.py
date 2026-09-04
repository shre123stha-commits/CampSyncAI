"""Human phrasing for a deadline countdown.

`days_remaining` is a plain signed integer from the backend. Rendering it
verbatim produces "-4d left" for anything already past, which reads as a bug
rather than as information. Moodle's "recent and upcoming" calendar export
routinely includes events whose due date has passed, so negatives are normal
and have to be phrased deliberately.
"""

from __future__ import annotations

# The backend uses this sentinel when a deadline could not be parsed, so the
# task sorts last instead of looking urgent. It is not a real countdown.
UNKNOWN_DEADLINE_DAYS = 999


def format_days_remaining(days: int | None) -> str:
    """Return a display phrase, or "" when there is nothing meaningful to say."""
    if not isinstance(days, int) or days >= UNKNOWN_DEADLINE_DAYS:
        return ""

    if days < 0:
        overdue = abs(days)
        unit = "day" if overdue == 1 else "days"
        return f"⚠️ overdue by {overdue} {unit}"

    if days == 0:
        return "⏳ due today"

    if days == 1:
        return "⏳ due tomorrow"

    return f"⏳ {days}d left"
