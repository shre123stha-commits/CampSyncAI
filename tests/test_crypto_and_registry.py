import pytest

from db.crypto import DecryptionError, decrypt, encrypt, try_decrypt
from db.models import SourceType
from models.task import Task
from sources.base import SourceError
from sources.registry import merge_tasks, task_key


# ---------------- encryption ----------------


def test_roundtrip():
    assert decrypt(encrypt("secret-token")) == "secret-token"


def test_ciphertext_hides_the_plaintext():
    assert "secret-token" not in encrypt("secret-token")


def test_encryption_is_non_deterministic():
    """Fernet includes a random IV, so two encryptions differ."""
    assert encrypt("same") != encrypt("same")


def test_unicode_roundtrip():
    value = "https://x.edu/feed?u=Ünïcøde–🎓"
    assert decrypt(encrypt(value)) == value


def test_long_value_roundtrip():
    value = "x" * 5000
    assert decrypt(encrypt(value)) == value


def test_corrupt_ciphertext_raises():
    with pytest.raises(DecryptionError):
        decrypt("not-a-valid-token")


def test_empty_ciphertext_raises():
    with pytest.raises(DecryptionError):
        decrypt("")


def test_try_decrypt_returns_none_instead_of_raising():
    assert try_decrypt("garbage") is None


def test_try_decrypt_passes_through_valid_values():
    assert try_decrypt(encrypt("ok")) == "ok"


def test_tampered_ciphertext_is_rejected():
    """Fernet is authenticated, so a modified token must not decrypt."""
    token = encrypt("secret")
    tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")

    with pytest.raises(DecryptionError):
        decrypt(tampered)


# ---------------- merging ----------------


def make(subject="Maths", work="PS3", deadline="12 August 2026"):
    return Task(
        subject=subject,
        task_type="Assignment",
        platform="LMS",
        deadline=deadline,
        work=work,
    )


def test_key_is_case_insensitive():
    assert task_key(make("Maths", "PS3")) == task_key(make("  maths", "ps3  "))


def test_merge_removes_duplicates_across_sources():
    merged = merge_tasks([make()], [make()])
    assert len(merged) == 1


def test_merge_keeps_distinct_tasks():
    merged = merge_tasks([make("Maths")], [make("Physics")])
    assert len(merged) == 2


def test_earlier_group_wins():
    documents = [make(work="From the document")]
    calendar = [make(work="From the document")]

    merged = merge_tasks(documents, calendar)

    assert merged[0].work == "From the document"


def test_merge_handles_empty_groups():
    assert merge_tasks([], [], []) == []


def test_merge_preserves_order():
    merged = merge_tasks([make("A"), make("B")], [make("C")])
    assert [t.subject for t in merged] == ["A", "B", "C"]


def test_different_deadlines_are_distinct():
    merged = merge_tasks(
        [make(deadline="12 August 2026")], [make(deadline="13 August 2026")]
    )
    assert len(merged) == 2


# ---------------- registry resilience ----------------


def test_source_type_enum_values():
    assert SourceType.ICS.value == "ics"
    assert SourceType.CLASSROOM.value == "classroom"


def test_source_error_is_an_exception():
    assert issubclass(SourceError, Exception)
