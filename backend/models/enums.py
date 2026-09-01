from enum import Enum


class PlanMode(str, Enum):
    """The four supported planning modes."""

    DAY_WITHOUT_TIMINGS = "day_without_timings"
    DAY_WITH_TIMINGS = "day_with_timings"
    WEEK_WITHOUT_TIMINGS = "week_without_timings"
    WEEK_WITH_TIMINGS = "week_with_timings"

    @property
    def includes_timings(self) -> bool:
        return self in {
            PlanMode.DAY_WITH_TIMINGS,
            PlanMode.WEEK_WITH_TIMINGS,
        }

    @property
    def is_weekly(self) -> bool:
        return self in {
            PlanMode.WEEK_WITH_TIMINGS,
            PlanMode.WEEK_WITHOUT_TIMINGS,
        }


class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
