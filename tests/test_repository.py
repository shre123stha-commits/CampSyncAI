import pytest
from sqlmodel import Session, SQLModel, create_engine

from db.models import SourceType, TaskRecord
from db.repository import (
    DuplicateStudentError,
    authenticate,
    completed_fingerprints,
    create_student,
    get_student,
    latest_plan,
    list_tasks,
    save_plan,
    set_task_completed,
    sync_tasks,
    task_fingerprint,
)
from models.task import Task


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def student(session):
    return create_student(session, "24BAI1127", "hunter22", "Asha")


def make_task(subject="Maths", work="Problem set 3", deadline="12 August 2026"):
    return Task(
        subject=subject,
        task_type="Assignment",
        platform="LMS",
        deadline=deadline,
        work=work,
    )


# ---------------- fingerprints ----------------


def test_fingerprint_is_stable():
    assert task_fingerprint("Maths", "PS3", "12 Aug") == task_fingerprint(
        "Maths", "PS3", "12 Aug"
    )


def test_fingerprint_ignores_case_and_padding():
    assert task_fingerprint("Maths", "PS3", "12 Aug") == task_fingerprint(
        "  maths ", "ps3", "12 AUG"
    )


def test_fingerprint_differs_by_content():
    a = task_fingerprint("Maths", "PS3", "12 Aug")
    assert a != task_fingerprint("Physics", "PS3", "12 Aug")
    assert a != task_fingerprint("Maths", "PS4", "12 Aug")
    assert a != task_fingerprint("Maths", "PS3", "13 Aug")


# ---------------- accounts ----------------


def test_create_and_fetch(session):
    create_student(session, "24BCE1085", "password1")
    assert get_student(session, "24BCE1085") is not None


def test_duplicate_registration_rejected(session, student):
    with pytest.raises(DuplicateStudentError):
        create_student(session, "24BAI1127", "another1")


def test_password_is_hashed_not_stored(session, student):
    assert student.password_hash != "hunter22"
    assert "hunter22" not in student.password_hash


def test_authenticate_success(session, student):
    assert authenticate(session, "24BAI1127", "hunter22") is not None


def test_authenticate_wrong_password(session, student):
    assert authenticate(session, "24BAI1127", "nope") is None


def test_authenticate_unknown_student(session):
    assert authenticate(session, "GHOST", "whatever") is None


def test_login_updates_last_login(session, student):
    assert student.last_login is None
    authenticate(session, "24BAI1127", "hunter22")
    assert get_student(session, "24BAI1127").last_login is not None


# ---------------- task sync ----------------


def test_sync_inserts_tasks(session, student):
    sync_tasks(session, student.id, [make_task(), make_task("Physics")])
    assert len(list_tasks(session, student.id)) == 2


def test_sync_is_idempotent(session, student):
    sync_tasks(session, student.id, [make_task()])
    sync_tasks(session, student.id, [make_task()])

    assert len(list_tasks(session, student.id)) == 1, "No duplicate rows"


def test_completion_survives_resync(session, student):
    """The core guarantee: re-reading documents must not un-tick a task."""
    records = sync_tasks(session, student.id, [make_task()])
    set_task_completed(session, student.id, records[0].id, True)

    sync_tasks(session, student.id, [make_task()])

    assert list_tasks(session, student.id)[0].completed is True


def test_sync_adds_new_tasks_without_touching_old(session, student):
    first = sync_tasks(session, student.id, [make_task()])
    set_task_completed(session, student.id, first[0].id, True)

    sync_tasks(session, student.id, [make_task(), make_task("Physics")])

    tasks = {t.subject: t for t in list_tasks(session, student.id)}
    assert len(tasks) == 2
    assert tasks["Maths"].completed is True
    assert tasks["Physics"].completed is False


def test_list_can_exclude_completed(session, student):
    records = sync_tasks(session, student.id, [make_task(), make_task("Physics")])
    set_task_completed(session, student.id, records[0].id, True)

    pending = list_tasks(session, student.id, include_completed=False)

    assert [t.subject for t in pending] == ["Physics"]


def test_toggle_completion_off(session, student):
    records = sync_tasks(session, student.id, [make_task()])

    set_task_completed(session, student.id, records[0].id, True)
    record = set_task_completed(session, student.id, records[0].id, False)

    assert record.completed is False
    assert record.completed_at is None


def test_completed_at_is_set(session, student):
    records = sync_tasks(session, student.id, [make_task()])
    record = set_task_completed(session, student.id, records[0].id, True)
    assert record.completed_at is not None


def test_cannot_complete_another_students_task(session, student):
    other = create_student(session, "24BCS1028", "password1")
    records = sync_tasks(session, student.id, [make_task()])

    assert set_task_completed(session, other.id, records[0].id, True) is None
    assert list_tasks(session, student.id)[0].completed is False


def test_completing_missing_task_returns_none(session, student):
    assert set_task_completed(session, student.id, 9999, True) is None


def test_completed_fingerprints(session, student):
    records = sync_tasks(session, student.id, [make_task(), make_task("Physics")])
    set_task_completed(session, student.id, records[0].id, True)

    prints = completed_fingerprints(session, student.id)

    assert prints == {task_fingerprint("Maths", "Problem set 3", "12 August 2026")}


def test_tasks_are_scoped_per_student(session, student):
    other = create_student(session, "24BCS1028", "password1")
    sync_tasks(session, student.id, [make_task()])

    assert list_tasks(session, other.id) == []


def test_source_is_recorded(session, student):
    sync_tasks(session, student.id, [make_task()], source=SourceType.UPLOAD)
    assert list_tasks(session, student.id)[0].source is SourceType.UPLOAD


# ---------------- plans ----------------


def test_save_and_fetch_plan(session, student):
    save_plan(session, student.id, "day_with_timings", {"plan": [{"a": 1}]})

    assert latest_plan(session, student.id, "day_with_timings") == {
        "plan": [{"a": 1}]
    }


def test_latest_plan_returns_most_recent(session, student):
    save_plan(session, student.id, "day_with_timings", {"v": 1})
    save_plan(session, student.id, "day_with_timings", {"v": 2})

    assert latest_plan(session, student.id, "day_with_timings")["v"] == 2


def test_latest_plan_missing_returns_none(session, student):
    assert latest_plan(session, student.id, "week_with_timings") is None
