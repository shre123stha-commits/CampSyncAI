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
    import db.security as security

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
