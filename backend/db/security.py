"""Password hashing and session tokens.

We hash a password the student chose **for this application**. We never
collect, transmit or store a university credential — every external
integration will use OAuth or a revocable, scoped token instead.
"""

from __future__ import annotations

import hashlib
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
# Recovery codes
# --------------------------------------------------------------------------
#
# This deployment has no email service, so "forgot password" cannot send a
# link. Instead each account gets one recovery code at sign-up, displayed
# once and never again. It is bcrypt-hashed exactly like a password, because
# that is what it is: anyone holding it can take over the account.

# Unambiguous alphabet: no O/0, I/1, so a code copied by hand still works.
RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

RECOVERY_GROUPS = 4
RECOVERY_GROUP_SIZE = 4


def generate_recovery_code() -> str:
    """A human-transcribable one-time code, e.g. 'K7QM-2XPD-9WRT-BH4N'."""
    groups = [
        "".join(
            secrets.choice(RECOVERY_ALPHABET) for _ in range(RECOVERY_GROUP_SIZE)
        )
        for _ in range(RECOVERY_GROUPS)
    ]
    return "-".join(groups)


def normalise_recovery_code(code: str) -> str:
    """Accept lowercase, missing dashes and stray spaces."""
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def hash_recovery_code(code: str) -> str:
    return bcrypt.hashpw(
        normalise_recovery_code(code).encode("utf-8"),
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
    ).decode("utf-8")


def verify_recovery_code(code: str, recovery_hash: str) -> bool:
    """Constant-time check. False on anything malformed or already consumed."""
    cleaned = normalise_recovery_code(code)

    if not cleaned or not recovery_hash:
        return False

    try:
        return bcrypt.checkpw(
            cleaned.encode("utf-8"), recovery_hash.encode("utf-8")
        )
    except (ValueError, TypeError) as exc:
        logger.warning("Recovery verification failed: %s", exc)
        return False


# --------------------------------------------------------------------------
# Session tokens
# --------------------------------------------------------------------------
#
# Sessions live in the database, not in process memory. An in-memory store
# signs every student out whenever the API restarts or is redeployed, and
# breaks outright behind more than one worker, since a token issued by one
# process is unknown to the next.
#
# Only a SHA-256 hash of the token is persisted. The plaintext exists solely
# in the client's hands, so a database leak yields no usable sessions.

TOKEN_BYTES = 32


def hash_token(token: str) -> str:
    """Hash a bearer token for storage. Unsalted SHA-256 is correct here:

    the token is 32 bytes of CSPRNG output, so it has no guessable structure
    for a rainbow table to exploit, and lookups must be exact-match.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(student_id: int) -> str:
    """Issue a token and persist its hash. Returns the plaintext token."""
    from db.models import AuthSession
    from db.session import session_scope

    token = secrets.token_urlsafe(TOKEN_BYTES)

    with session_scope() as session:
        session.add(
            AuthSession(
                student_id=student_id,
                token_hash=hash_token(token),
                expires_at=datetime.utcnow()
                + timedelta(hours=SESSION_TTL_HOURS),
            )
        )

    return token


def resolve_session(token: str) -> int | None:
    """Return the student id for *token*, or None if absent/expired."""
    if not token:
        return None

    from sqlmodel import select

    from db.models import AuthSession
    from db.session import session_scope

    with session_scope() as session:
        record = session.exec(
            select(AuthSession).where(AuthSession.token_hash == hash_token(token))
        ).first()

        if record is None:
            return None

        if datetime.utcnow() >= record.expires_at:
            session.delete(record)
            return None

        return record.student_id


def destroy_session(token: str) -> None:
    if not token:
        return

    from sqlmodel import select

    from db.models import AuthSession
    from db.session import session_scope

    with session_scope() as session:
        record = session.exec(
            select(AuthSession).where(AuthSession.token_hash == hash_token(token))
        ).first()

        if record is not None:
            session.delete(record)


def purge_expired_sessions() -> int:
    """Delete sessions past their expiry. Returns how many were removed."""
    from sqlmodel import select

    from db.models import AuthSession
    from db.session import session_scope

    with session_scope() as session:
        stale = session.exec(
            select(AuthSession).where(AuthSession.expires_at < datetime.utcnow())
        ).all()

        for record in stale:
            session.delete(record)

    if stale:
        logger.info("Purged %d expired session(s)", len(stale))

    return len(stale)


def clear_sessions() -> None:
    """Used by tests. Tolerates a database whose tables do not exist yet."""
    from sqlalchemy.exc import SQLAlchemyError
    from sqlmodel import select

    from db.models import AuthSession
    from db.session import session_scope

    try:
        with session_scope() as session:
            for record in session.exec(select(AuthSession)).all():
                session.delete(record)
    except SQLAlchemyError:
        pass
