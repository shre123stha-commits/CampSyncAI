"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from config import DATABASE_URL, get_logger

logger = get_logger(__name__)

# check_same_thread=False is required because FastAPI serves requests from a
# threadpool while SQLite defaults to single-thread ownership.
_connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(DATABASE_URL, echo=False, connect_args=_connect_args)


def set_engine(new_engine) -> None:
    """Point every session at *new_engine*.

    Tests swap in an in-memory database. Without this, code that opens its own
    session (rather than receiving one through FastAPI's dependency system)
    would keep writing to the real file.
    """
    global engine
    engine = new_engine


def init_db() -> None:
    """Create any missing tables. Safe to call on every startup."""
    # Importing registers the models on SQLModel.metadata.
    import db.models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    logger.info("Database ready at %s", DATABASE_URL)


@contextmanager
def session_scope() -> Iterator[Session]:
    """A transactional session: commits on success, rolls back on error."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with Session(engine) as session:
        yield session
