"""The extraction cache must remove LLM calls without going stale."""

from datetime import datetime

import pytest

import agents.academic_agent as academic
import utils.cache as cache_module
from models.task import Task
from models.timetable import Lecture


@pytest.fixture(autouse=True)
def temp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_module, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(cache_module, "CACHE_ENABLED", True)


@pytest.fixture
def docs(tmp_path, monkeypatch):
    """Two fake .docx files plus a call counter for the extractors."""
    timetable_dir = tmp_path / "timetable"
    lms_dir = tmp_path / "lms"
    timetable_dir.mkdir()
    lms_dir.mkdir()

    (timetable_dir / "24BAI1127.docx").write_text("timetable")
    (lms_dir / "24BAI1127.docx").write_text("lms")

    monkeypatch.setattr(academic, "TIMETABLE_DIR", timetable_dir)
    monkeypatch.setattr(academic, "LMS_DIR", lms_dir)
    monkeypatch.setattr(academic, "read_docx", lambda path: path.read_text())

    calls = {"timetable": 0, "tasks": 0}

    def fake_timetable(text):
        calls["timetable"] += 1
        return [
            Lecture(
                day="Monday",
                start_time="09:00",
                end_time="10:00",
                subject="Maths",
            )
        ]

    def fake_tasks(text, platform):
        calls["tasks"] += 1
        return [
            Task(
                subject="Maths",
                task_type="Assignment",
                platform=platform,
                deadline="12 August 2026",
                work="Problem set 3",
            )
        ]

    monkeypatch.setattr(academic, "extract_timetable", fake_timetable)
    monkeypatch.setattr(academic, "extract_tasks", fake_tasks)

    return {"dir": tmp_path, "calls": calls, "timetable_dir": timetable_dir}


def test_first_call_extracts(docs):
    lectures, tasks = academic.load_academic_data("24BAI1127")

    assert docs["calls"] == {"timetable": 1, "tasks": 1}
    assert len(lectures) == 1
    assert len(tasks) == 1


def test_second_call_uses_cache(docs):
    academic.load_academic_data("24BAI1127")
    academic.load_academic_data("24BAI1127")

    assert docs["calls"] == {"timetable": 1, "tasks": 1}, (
        "The extractors must not run again on a cache hit"
    )


def test_cached_data_is_equivalent(docs):
    first_lectures, first_tasks = academic.load_academic_data("24BAI1127")
    second_lectures, second_tasks = academic.load_academic_data("24BAI1127")

    assert [x.model_dump() for x in first_lectures] == [
        x.model_dump() for x in second_lectures
    ]
    assert [x.subject for x in first_tasks] == [x.subject for x in second_tasks]


def test_editing_a_document_invalidates_the_cache(docs):
    academic.load_academic_data("24BAI1127")

    doc = docs["timetable_dir"] / "24BAI1127.docx"
    doc.write_text("a substantially edited timetable document")

    academic.load_academic_data("24BAI1127")

    assert docs["calls"]["timetable"] == 2


def test_days_remaining_is_recomputed_not_cached(docs, monkeypatch):
    """A cached days_remaining would be wrong the next morning."""
    academic.load_academic_data("24BAI1127")

    class FrozenDate(datetime):
        @classmethod
        def today(cls):
            return datetime(2026, 8, 10)

    monkeypatch.setattr(academic, "datetime", FrozenDate)

    _, tasks = academic.load_academic_data("24BAI1127")

    # 12 August 2026 minus 10 August 2026
    assert tasks[0].days_remaining == 2
    assert docs["calls"]["tasks"] == 1, "Still served from cache"


def test_unknown_student_raises(docs):
    with pytest.raises(academic.StudentNotFoundError):
        academic.load_academic_data("NOPE")


def test_missing_timetable_still_loads_tasks(docs, monkeypatch):
    (docs["timetable_dir"] / "24BAI1127.docx").unlink()

    lectures, tasks = academic.load_academic_data("24BAI1127")

    assert lectures == []
    assert len(tasks) == 1
