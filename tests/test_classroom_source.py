"""Google Classroom normalisation and configuration guards.

No network calls: the Google client is never invoked in these tests.
"""

import pytest

import config
from sources.base import SourceError
from sources.classroom_source import (
    ClassroomSource,
    _parse_due,
    build_flow,
    coursework_to_tasks,
)


# ---------------- configuration guards ----------------


def test_build_flow_requires_configuration(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "")

    import sources.classroom_source as module

    monkeypatch.setattr(module, "classroom_configured", lambda: False)

    with pytest.raises(SourceError, match="not configured"):
        build_flow()


def test_fetch_without_token_raises():
    with pytest.raises(SourceError, match="not connected"):
        ClassroomSource().fetch({})


def test_source_metadata():
    source = ClassroomSource()
    assert source.name == "Google Classroom"
    assert source.source_type.value == "classroom"


# ---------------- due date parsing ----------------


def test_parse_due_date():
    assert (
        _parse_due({"dueDate": {"year": 2026, "month": 9, "day": 10}})
        == "10 September 2026"
    )


def test_missing_due_date_is_blank():
    assert _parse_due({}) == ""


def test_malformed_due_date_is_blank():
    assert _parse_due({"dueDate": {"year": 2026}}) == ""
    assert _parse_due({"dueDate": {"year": 2026, "month": 13, "day": 40}}) == ""


# ---------------- coursework normalisation ----------------


COURSES = [
    {"id": "c1", "name": "Machine Learning"},
    {"id": "c2", "name": "Databases"},
]


def test_normalises_coursework():
    coursework = {
        "c1": [
            {
                "title": "Assignment 3",
                "workType": "ASSIGNMENT",
                "dueDate": {"year": 2026, "month": 9, "day": 10},
                "state": "PUBLISHED",
            }
        ],
        "c2": [],
    }

    tasks = coursework_to_tasks(COURSES, coursework)

    assert len(tasks) == 1
    assert tasks[0].subject == "Machine Learning"
    assert tasks[0].platform == "Google Classroom"
    assert tasks[0].deadline == "10 September 2026"
    assert tasks[0].task_type == "Assignment"


def test_quiz_work_types_are_mapped():
    coursework = {
        "c1": [
            {"title": "Q1", "workType": "SHORT_ANSWER_QUESTION"},
            {"title": "Q2", "workType": "MULTIPLE_CHOICE_QUESTION"},
        ]
    }

    assert [t.task_type for t in coursework_to_tasks(COURSES, coursework)] == [
        "Quiz",
        "Quiz",
    ]


def test_unpublished_work_is_skipped():
    coursework = {
        "c1": [
            {"title": "Draft", "state": "DRAFT"},
            {"title": "Live", "state": "PUBLISHED"},
        ]
    }

    tasks = coursework_to_tasks(COURSES, coursework)

    assert [t.work for t in tasks] == ["Live"]


def test_unknown_course_falls_back():
    tasks = coursework_to_tasks([], {"zzz": [{"title": "Orphan"}]})
    assert tasks[0].subject == "Course"


def test_missing_due_date_yields_empty_deadline():
    tasks = coursework_to_tasks(COURSES, {"c1": [{"title": "No deadline"}]})
    assert tasks[0].deadline == ""


def test_description_used_when_title_missing():
    tasks = coursework_to_tasks(
        COURSES, {"c1": [{"description": "Read chapter 4"}]}
    )
    assert tasks[0].work == "Read chapter 4"


def test_empty_coursework():
    assert coursework_to_tasks(COURSES, {}) == []
