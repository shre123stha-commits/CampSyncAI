"""End-to-end auth and task-completion flow against the real app."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import agents.academic_agent as academic
import api.main as api_main
import db.models  # noqa: F401 - registers the tables on SQLModel.metadata
from db.security import clear_sessions
import db.session as db_session
from db.session import get_session
from models.task import Task
from models.timetable import Lecture


@pytest.fixture
def client(monkeypatch, tmp_path):
    """A client backed by a fresh in-memory database.

    StaticPool keeps every connection pointed at the *same* in-memory
    database; without it each connection would get its own empty one.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    # Code that opens its own session (session persistence) must use the
    # test engine too, not the real database file.
    db_session.set_engine(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    api_main.app.dependency_overrides[get_session] = override_session
    clear_sessions()

    # Two extracted tasks, no LLM involved.
    monkeypatch.setattr(
        academic,
        "load_academic_data",
        lambda reg: (
            [
                Lecture(
                    day="Monday",
                    start_time="09:00",
                    end_time="10:00",
                    subject="Maths",
                )
            ],
            [
                Task(
                    subject="Maths",
                    task_type="Assignment",
                    platform="LMS",
                    deadline="12 August 2026",
                    work="Problem set 3",
                ),
                Task(
                    subject="Physics",
                    task_type="Quiz",
                    platform="LMS",
                    deadline="20 December 2026",
                    work="Revise optics",
                ),
            ],
        ),
    )
    import api.routes_tasks as routes_tasks

    monkeypatch.setattr(
        routes_tasks, "load_academic_data", academic.load_academic_data
    )

    with TestClient(api_main.app, raise_server_exceptions=False) as test_client:
        yield test_client

    api_main.app.dependency_overrides.clear()


def register(client, reg="24BAI1127", password="hunter22"):
    return client.post(
        "/auth/register",
        json={"registration_no": reg, "password": password, "name": "Asha"},
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- registration ----------------


def test_register_returns_token(client):
    response = register(client)
    assert response.status_code == 201
    assert response.json()["token"]


def test_duplicate_registration_409(client):
    register(client)
    assert register(client).status_code == 409


def test_short_password_rejected(client):
    response = client.post(
        "/auth/register",
        json={"registration_no": "X1", "password": "abc"},
    )
    assert response.status_code == 422


def test_password_never_returned(client):
    assert "hunter22" not in register(client).text


# ---------------- login ----------------


def test_login_success(client):
    register(client)
    response = client.post(
        "/auth/login",
        json={"registration_no": "24BAI1127", "password": "hunter22"},
    )
    assert response.status_code == 200
    assert response.json()["token"]


def test_login_wrong_password_401(client):
    register(client)
    response = client.post(
        "/auth/login",
        json={"registration_no": "24BAI1127", "password": "wrong"},
    )
    assert response.status_code == 401


def test_login_unknown_user_401(client):
    response = client.post(
        "/auth/login",
        json={"registration_no": "GHOST", "password": "whatever"},
    )
    assert response.status_code == 401


def test_login_error_does_not_reveal_whether_account_exists(client):
    register(client)

    wrong_password = client.post(
        "/auth/login",
        json={"registration_no": "24BAI1127", "password": "wrong"},
    ).json()["detail"]

    no_account = client.post(
        "/auth/login",
        json={"registration_no": "GHOST", "password": "wrong"},
    ).json()["detail"]

    assert wrong_password == no_account


# ---------------- protected routes ----------------


def test_tasks_requires_auth(client):
    assert client.get("/tasks").status_code == 401


def test_bad_scheme_rejected(client):
    response = client.get("/tasks", headers={"Authorization": "Basic abc"})
    assert response.status_code == 401


def test_invalid_token_rejected(client):
    response = client.get("/tasks", headers=auth_header("made-up"))
    assert response.status_code == 401


def test_logout_invalidates_token(client):
    token = register(client).json()["token"]

    assert client.get("/tasks", headers=auth_header(token)).status_code == 200

    client.post("/auth/logout", headers=auth_header(token))

    assert client.get("/tasks", headers=auth_header(token)).status_code == 401


def test_me_endpoint(client):
    token = register(client).json()["token"]
    body = client.get("/auth/me", headers=auth_header(token)).json()
    assert body["registration_no"] == "24BAI1127"
    assert body["name"] == "Asha"


# ---------------- tasks ----------------


def test_tasks_returns_synced_tasks(client):
    token = register(client).json()["token"]

    body = client.get("/tasks", headers=auth_header(token)).json()

    assert body["stats"]["total"] == 2
    assert body["stats"]["pending"] == 2
    assert {t["subject"] for t in body["tasks"]} == {"Maths", "Physics"}


def test_tasks_have_ids_and_priority(client):
    token = register(client).json()["token"]

    task = client.get("/tasks", headers=auth_header(token)).json()["tasks"][0]

    assert isinstance(task["id"], int)
    assert task["priority"] in {"High", "Medium", "Low"}


def test_complete_a_task(client):
    token = register(client).json()["token"]
    task_id = client.get("/tasks", headers=auth_header(token)).json()["tasks"][0][
        "id"
    ]

    response = client.patch(
        f"/tasks/{task_id}",
        json={"completed": True},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["completed"] is True


def test_completion_persists_across_requests(client):
    token = register(client).json()["token"]
    task_id = client.get("/tasks", headers=auth_header(token)).json()["tasks"][0][
        "id"
    ]

    client.patch(
        f"/tasks/{task_id}", json={"completed": True}, headers=auth_header(token)
    )

    body = client.get("/tasks", headers=auth_header(token)).json()

    assert body["stats"]["completed"] == 1
    assert body["stats"]["pending"] == 1


def test_completed_tasks_can_be_filtered_out(client):
    token = register(client).json()["token"]
    task_id = client.get("/tasks", headers=auth_header(token)).json()["tasks"][0][
        "id"
    ]

    client.patch(
        f"/tasks/{task_id}", json={"completed": True}, headers=auth_header(token)
    )

    body = client.get(
        "/tasks?include_completed=false", headers=auth_header(token)
    ).json()

    assert body["stats"]["total"] == 1


def test_completed_tasks_sort_last(client):
    token = register(client).json()["token"]
    tasks = client.get("/tasks", headers=auth_header(token)).json()["tasks"]

    client.patch(
        f"/tasks/{tasks[0]['id']}",
        json={"completed": True},
        headers=auth_header(token),
    )

    after = client.get("/tasks", headers=auth_header(token)).json()["tasks"]

    assert after[-1]["completed"] is True


def test_cannot_complete_another_students_task(client):
    token_a = register(client).json()["token"]
    task_id = client.get("/tasks", headers=auth_header(token_a)).json()["tasks"][
        0
    ]["id"]

    token_b = register(client, "24BCS1028").json()["token"]

    response = client.patch(
        f"/tasks/{task_id}",
        json={"completed": True},
        headers=auth_header(token_b),
    )

    assert response.status_code == 404


def test_students_are_isolated(client):
    token_a = register(client).json()["token"]
    client.get("/tasks", headers=auth_header(token_a))

    token_b = register(client, "24BCS1028").json()["token"]
    body_b = client.get("/tasks", headers=auth_header(token_b)).json()

    # B gets their own rows, not A's.
    ids_a = {
        t["id"]
        for t in client.get("/tasks", headers=auth_header(token_a)).json()["tasks"]
    }
    ids_b = {t["id"] for t in body_b["tasks"]}

    assert ids_a.isdisjoint(ids_b)


def test_missing_task_404(client):
    token = register(client).json()["token"]

    response = client.patch(
        "/tasks/99999", json={"completed": True}, headers=auth_header(token)
    )

    assert response.status_code == 404


# ---------------- upload ----------------


def test_upload_requires_auth(client):
    response = client.post(
        "/upload?kind=timetable",
        files={"file": ("t.docx", b"data", "application/octet-stream")},
    )
    assert response.status_code == 401


def test_upload_rejects_bad_kind(client):
    token = register(client).json()["token"]

    response = client.post(
        "/upload?kind=nonsense",
        files={"file": ("t.docx", b"data", "application/octet-stream")},
        headers=auth_header(token),
    )

    assert response.status_code == 422


def test_upload_rejects_wrong_extension(client):
    token = register(client).json()["token"]

    response = client.post(
        "/upload?kind=timetable",
        files={"file": ("t.exe", b"data", "application/octet-stream")},
        headers=auth_header(token),
    )

    assert response.status_code == 422


def test_upload_rejects_empty_file(client):
    token = register(client).json()["token"]

    response = client.post(
        "/upload?kind=timetable",
        files={"file": ("t.docx", b"", "application/octet-stream")},
        headers=auth_header(token),
    )

    assert response.status_code == 422


def test_upload_succeeds(client, tmp_path, monkeypatch):
    import api.routes_tasks as routes_tasks

    monkeypatch.setattr(routes_tasks, "UPLOAD_DIR", tmp_path)

    token = register(client).json()["token"]

    response = client.post(
        "/upload?kind=timetable",
        files={"file": ("t.docx", b"fake docx bytes", "application/octet-stream")},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert (tmp_path / "timetable" / "24BAI1127.docx").exists()


def test_upload_too_large(client, monkeypatch):
    import api.routes_tasks as routes_tasks

    monkeypatch.setattr(routes_tasks, "MAX_UPLOAD_BYTES", 10)

    token = register(client).json()["token"]

    response = client.post(
        "/upload?kind=lms",
        files={"file": ("t.docx", b"x" * 100, "application/octet-stream")},
        headers=auth_header(token),
    )

    assert response.status_code == 413
