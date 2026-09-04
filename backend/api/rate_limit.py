"""A small per-account rate limiter for the expensive endpoints.

Plan generation is the only operation that costs real money or real time: it
calls a language model. Without a limit, one person holding down "Regenerate"
can exhaust a free API tier for everyone else, or run up a bill.

This is a fixed-window counter held in process memory. That is the right size
for a small deployment: no Redis, no extra service, and the worst case if the
process restarts is that a few counters reset early. It does *not* coordinate
across multiple workers - if this ever runs behind more than one, move the
counters into the database or Redis.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from datetime import datetime, timedelta

from config import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Allow `limit` events per `window` per key."""

    def __init__(self, limit: int, window_minutes: int, name: str = "requests"):
        self.limit = limit
        self.window = timedelta(minutes=window_minutes)
        self.name = name

        # Requests are served from a threadpool, so the counters need a lock.
        self._lock = threading.Lock()
        self._hits: dict[str, list[datetime]] = defaultdict(list)

    def check(self, key: str, now: datetime | None = None) -> tuple[bool, int]:
        """Record an attempt. Returns (allowed, seconds_until_retry).

        `seconds_until_retry` is 0 when allowed.
        """
        moment = now or datetime.utcnow()
        cutoff = moment - self.window

        with self._lock:
            recent = [stamp for stamp in self._hits[key] if stamp > cutoff]

            if len(recent) >= self.limit:
                # Oldest hit in the window decides when a slot frees up.
                retry_after = int((recent[0] + self.window - moment).total_seconds())
                self._hits[key] = recent
                logger.info(
                    "Rate limit hit for %s (%s): %d in the last %s",
                    key,
                    self.name,
                    len(recent),
                    self.window,
                )
                return False, max(retry_after, 1)

            recent.append(moment)
            self._hits[key] = recent

            return True, 0

    def reset(self, key: str | None = None) -> None:
        """Clear counters. Used by tests and by admin intervention."""
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


# Plan generation is the expensive path. Ten per hour is far above normal use
# - a student generates a handful a day - while capping a stuck retry loop.
plan_limiter = RateLimiter(limit=10, window_minutes=60, name="plan generation")

# Sign-in attempts, to slow down guessing at a friend's password.
login_limiter = RateLimiter(limit=10, window_minutes=15, name="login")

# Recovery codes are as powerful as passwords, so guessing gets a tighter cap.
reset_limiter = RateLimiter(limit=5, window_minutes=60, name="password reset")
