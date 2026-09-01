"""Password hashing and session tokens.

We hash a password the student chose **for this application**. We never
collect, transmit or store a university credential — every external
integration will use OAuth or a revocable, scoped token instead.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

import bcrypt

from config import SESSION_TTL_HOURS, get_logger

logger = get_logger(__name__)

BCRYPT_ROUNDS = 12

# bcrypt silently truncates beyond 72 bytes, so reject longer input outright
# rather than accepting a password whose tail is ignored.
MAX_PASSWORD_BYTES = 72

MIN_PASSWORD_LENGTH = 6


class PasswordError(ValueError):
    """The supplied password is not acceptable."""


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )

    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise PasswordError("Password is too long (maximum 72 bytes).")


def hash_password(password: str) -> str:
    validate_password(password)

    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time verification. Never raises on malformed input."""
    if not password or not password_hash:
        return False

    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:MAX_PASSWORD_BYTES],
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError) as exc:
        logger.warning("Password verification failed: %s", exc)
        return False


# --------------------------------------------------------------------------
# Session tokens
# --------------------------------------------------------------------------
#
# An in-process token store. Adequate for a single-instance deployment; swap
# for Redis or signed JWTs when running more than one worker.

_sessions: dict[str, tuple[int, datetime]] = {}


def create_session(student_id: int) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = (
        student_id,
        datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS),
    )
    return token


def resolve_session(token: str) -> int | None:
    """Return the student id for *token*, or None if absent/expired."""
    entry = _sessions.get(token)

    if entry is None:
        return None

    student_id, expires_at = entry

    if datetime.utcnow() >= expires_at:
        _sessions.pop(token, None)
        return None

    return student_id


def destroy_session(token: str) -> None:
    _sessions.pop(token, None)


def clear_sessions() -> None:
    """Used by tests."""
    _sessions.clear()
