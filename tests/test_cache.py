import json

import pytest

import utils.cache as cache_module
from utils.cache import cache_clear, cache_get, cache_set, fingerprint_files


@pytest.fixture(autouse=True)
def temp_cache(tmp_path, monkeypatch):
    """Isolate every test in its own cache directory."""
    monkeypatch.setattr(cache_module, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache_module, "CACHE_ENABLED", True)
    return tmp_path


# ---------------- fingerprinting ----------------


def test_fingerprint_is_stable(tmp_path):
    doc = tmp_path / "a.docx"
    doc.write_text("hello")

    assert fingerprint_files(doc) == fingerprint_files(doc)


def test_fingerprint_changes_when_size_changes(tmp_path):
    doc = tmp_path / "a.docx"
    doc.write_text("hello")
    before = fingerprint_files(doc)

    doc.write_text("hello world, considerably longer")

    assert fingerprint_files(doc) != before


def test_fingerprint_handles_missing_files(tmp_path):
    missing = tmp_path / "nope.docx"
    assert isinstance(fingerprint_files(missing), str)


def test_fingerprint_missing_differs_from_present(tmp_path):
    doc = tmp_path / "a.docx"
    missing = tmp_path / "a_missing.docx"
    doc.write_text("x")

    assert fingerprint_files(doc) != fingerprint_files(missing)


def test_fingerprint_is_order_independent(tmp_path):
    one = tmp_path / "one.docx"
    two = tmp_path / "two.docx"
    one.write_text("1")
    two.write_text("2")

    assert fingerprint_files(one, two) == fingerprint_files(two, one)


# ---------------- get / set ----------------


def test_miss_returns_none():
    assert cache_get("ns", "absent") is None


def test_roundtrip():
    cache_set("ns", "k", {"tasks": [1, 2, 3]})
    assert cache_get("ns", "k") == {"tasks": [1, 2, 3]}


def test_namespaces_are_isolated():
    cache_set("a", "k", "from-a")
    cache_set("b", "k", "from-b")

    assert cache_get("a", "k") == "from-a"
    assert cache_get("b", "k") == "from-b"


def test_unicode_survives_roundtrip():
    cache_set("ns", "k", {"subject": "Máths — Álgebra 🎓"})
    assert cache_get("ns", "k")["subject"] == "Máths — Álgebra 🎓"


def test_key_with_unsafe_characters(tmp_path):
    cache_set("ns", "24BAI/1127:v1", {"ok": True})
    assert cache_get("ns", "24BAI/1127:v1") == {"ok": True}


def test_corrupt_entry_is_discarded(temp_cache):
    cache_set("ns", "k", {"ok": True})

    corrupt = temp_cache / "ns" / "k.json"
    corrupt.write_text("{ this is not json")

    assert cache_get("ns", "k") is None
    assert not corrupt.exists(), "A corrupt entry should be removed"


def test_disabled_cache_is_a_no_op(monkeypatch):
    monkeypatch.setattr(cache_module, "CACHE_ENABLED", False)

    cache_set("ns", "k", {"ok": True})

    assert cache_get("ns", "k") is None


def test_write_failure_does_not_raise(monkeypatch, temp_cache):
    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(cache_module.Path, "mkdir", boom)

    # Must not propagate - a cache failure cannot break the request.
    cache_set("ns", "k", {"ok": True})


def test_written_file_is_valid_json(temp_cache):
    cache_set("ns", "k", {"a": 1})

    with (temp_cache / "ns" / "k.json").open() as handle:
        assert json.load(handle) == {"a": 1}


# ---------------- clearing ----------------


def test_clear_single_key():
    cache_set("ns", "k1", 1)
    cache_set("ns", "k2", 2)

    assert cache_clear("ns", "k1") == 1
    assert cache_get("ns", "k1") is None
    assert cache_get("ns", "k2") == 2


def test_clear_namespace():
    cache_set("ns", "k1", 1)
    cache_set("ns", "k2", 2)
    cache_set("other", "k3", 3)

    assert cache_clear("ns") == 2
    assert cache_get("other", "k3") == 3


def test_clear_everything():
    cache_set("a", "k", 1)
    cache_set("b", "k", 2)

    assert cache_clear() == 2


def test_clear_missing_namespace_is_zero():
    assert cache_clear("never-used") == 0
