import pytest
from db.security import (
    MAX_PASSWORD_BYTES,
    PasswordError,
    clear_sessions,
    create_session,
    destroy_session,
    hash_password,
    resolve_session,
    validate_password,
    verify_password,
)


@pytest.fixture(autouse=True)
def _clean_sessions():
    clear_sessions()
    yield
    clear_sessions()


# ---------------- hashing ----------------


def test_hash_is_not_the_plaintext():
    hashed = hash_password("correct horse")
    assert hashed != "correct horse"
    assert "correct horse" not in hashed


def test_hash_is_salted():
    """Two hashes of the same password must differ."""
    assert hash_password("samepass") != hash_password("samepass")


def test_verify_accepts_correct_password():
    assert verify_password("s3cret!", hash_password("s3cret!"))


def test_verify_rejects_wrong_password():
    assert not verify_password("wrong", hash_password("s3cret!"))


def test_verify_is_case_sensitive():
    assert not verify_password("SECRET", hash_password("secret"))


def test_verify_handles_garbage_hash_without_raising():
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_verify_handles_empty_input():
    assert not verify_password("", hash_password("x" * 8))
    assert not verify_password("pass", "")


def test_unicode_password():
    hashed = hash_password("pässwörd–🎓")
    assert verify_password("pässwörd–🎓", hashed)
    assert not verify_password("passwoerd", hashed)


# ---------------- policy ----------------


def test_short_password_rejected():
    with pytest.raises(PasswordError):
        validate_password("abc")


def test_minimum_length_accepted():
    validate_password("abcdef")


def test_overlong_password_rejected():
    """bcrypt truncates past 72 bytes, so we reject rather than silently
    ignore the tail."""
    with pytest.raises(PasswordError):
        validate_password("a" * (MAX_PASSWORD_BYTES + 1))


def test_multibyte_length_counted_in_bytes():
    with pytest.raises(PasswordError):
        validate_password("🎓" * 20)  # 80 bytes


# ---------------- sessions ----------------


@pytest.fixture(autouse=True)
def _session_db(tmp_path):
    """Sessions are persisted, so these tests need a real (temporary) database."""
    import db.session as db_session
    from sqlmodel import SQLModel, create_engine

    engine = create_engine(f"sqlite:///{tmp_path / 'sessions.db'}")
    SQLModel.metadata.create_all(engine)
    db_session.set_engine(engine)
    yield


def test_session_roundtrip():
    token = create_session(42)
    assert resolve_session(token) == 42


def test_tokens_are_unique():
    assert create_session(1) != create_session(1)


def test_unknown_token_resolves_to_none():
    assert resolve_session("made-up-token") is None


def test_destroyed_session_is_gone():
    token = create_session(7)
    destroy_session(token)
    assert resolve_session(token) is None


def test_expired_session_resolves_to_none(monkeypatch):
    from db import security

    token = create_session(9)

    # Fast-forward past the TTL.
    from datetime import datetime, timedelta

    class Later(datetime):
        @classmethod
        def utcnow(cls):
            return datetime.now() + timedelta(days=365)

    monkeypatch.setattr(security, "datetime", Later)

    assert resolve_session(token) is None


def test_token_is_long_enough_to_be_unguessable():
    assert len(create_session(1)) >= 32


# --- Session persistence --------------------------------------------------
# An in-memory session store signs every student out on restart and breaks
# entirely behind more than one worker. These tests pin the fix.


def test_session_survives_a_process_restart(tmp_path, monkeypatch):
    """The property that matters: restarting the API must not log anyone out."""
    import db.session as db_session
    from db import security
    from sqlmodel import SQLModel, create_engine

    db_file = tmp_path / "restart.db"
    engine = create_engine(f"sqlite:///{db_file}")
    SQLModel.metadata.create_all(engine)
    db_session.set_engine(engine)

    token = security.create_session(42)

    # Simulate a restart: a brand new engine over the same file, which is
    # exactly what a redeploy or `uvicorn --reload` produces.
    reborn = create_engine(f"sqlite:///{db_file}")
    db_session.set_engine(reborn)

    assert security.resolve_session(token) == 42


def test_only_a_hash_of_the_token_is_stored(tmp_path):
    """A database leak must not hand over usable session tokens."""
    import db.session as db_session
    from db import security
    from db.models import AuthSession
    from sqlmodel import Session, SQLModel, create_engine, select

    engine = create_engine(f"sqlite:///{tmp_path / 'hash.db'}")
    SQLModel.metadata.create_all(engine)
    db_session.set_engine(engine)

    token = security.create_session(7)

    with Session(engine) as session:
        stored = session.exec(select(AuthSession)).one()

    assert token not in stored.token_hash
    assert stored.token_hash == security.hash_token(token)
    assert len(stored.token_hash) == 64  # sha256 hex


def test_expired_sessions_are_purged(tmp_path):
    from datetime import datetime, timedelta

    import db.session as db_session
    from db import security
    from db.models import AuthSession
    from sqlmodel import Session, SQLModel, create_engine, select

    engine = create_engine(f"sqlite:///{tmp_path / 'purge.db'}")
    SQLModel.metadata.create_all(engine)
    db_session.set_engine(engine)

    live = security.create_session(1)
    dead = security.create_session(2)

    with Session(engine) as session:
        record = session.exec(
            select(AuthSession).where(
                AuthSession.token_hash == security.hash_token(dead)
            )
        ).one()
        record.expires_at = datetime.utcnow() - timedelta(hours=1)
        session.add(record)
        session.commit()

    assert security.purge_expired_sessions() == 1
    assert security.resolve_session(live) == 1
    assert security.resolve_session(dead) is None
