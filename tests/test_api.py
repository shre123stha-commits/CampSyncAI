"""API contract tests. The graph is stubbed, so no LLM is required."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import api.main as api_main  # noqa: E402
from agents.academic_agent import StudentNotFoundError  # noqa: E402
from models.enums import PlanMode  # noqa: E402
from models.study_plan import PlannedItem, StudyPlanResponse  # noqa: E402
from utils.llm_json import LLMOutputError  # noqa: E402


@pytest.fixture
def client():
    return TestClient(api_main.app, raise_server_exceptions=False)


class StubGraph:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def invoke(self, state):
        if self.error:
            raise self.error
        return self.result


def ok_plan():
    return {
        "study_plan": StudyPlanResponse(
            mode=PlanMode.DAY_WITHOUT_TIMINGS,
            registration_no="24BAI1127",
            plan=[PlannedItem(subject="Maths", days_remaining=2)],
        )
    }


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_home(client):
    assert "CampusSync" in client.get("/").json()["message"]


def test_students_endpoint(client):
    body = client.get("/students").json()
    assert "students" in body
    assert isinstance(body["students"], list)


def test_generate_plan_success(client, monkeypatch):
    monkeypatch.setattr(api_main, "graph", StubGraph(result=ok_plan()))

    response = client.post(
        "/generate-plan",
        json={"registration_no": "24BAI1127", "mode": "day_without_timings"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "day_without_timings"
    assert body["plan"][0]["subject"] == "Maths"


def test_invalid_mode_returns_422(client):
    response = client.post(
        "/generate-plan",
        json={"registration_no": "24BAI1127", "mode": "monthly"},
    )
    assert response.status_code == 422


def test_empty_registration_returns_422(client):
    response = client.post(
        "/generate-plan",
        json={"registration_no": "", "mode": "day_with_timings"},
    )
    assert response.status_code == 422


def test_unknown_student_returns_404(client, monkeypatch):
    monkeypatch.setattr(
        api_main,
        "graph",
        StubGraph(error=StudentNotFoundError("No documents for 'NOPE'.")),
    )

    response = client.post(
        "/generate-plan",
        json={"registration_no": "NOPE", "mode": "day_with_timings"},
    )

    assert response.status_code == 404
    assert "NOPE" in response.json()["detail"]


def test_ollama_down_returns_503(client, monkeypatch):
    monkeypatch.setattr(
        api_main,
        "graph",
        StubGraph(error=LLMOutputError("LLM service error: connection refused")),
    )

    response = client.post(
        "/generate-plan",
        json={"registration_no": "24BAI1127", "mode": "day_with_timings"},
    )

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_invalid_llm_output_returns_502(client, monkeypatch):
    monkeypatch.setattr(
        api_main,
        "graph",
        StubGraph(error=LLMOutputError("planning: no valid output")),
    )

    response = client.post(
        "/generate-plan",
        json={"registration_no": "24BAI1127", "mode": "day_with_timings"},
    )

    assert response.status_code == 502


def test_unexpected_error_returns_500_without_leaking_details(
    client, monkeypatch
):
    monkeypatch.setattr(
        api_main,
        "graph",
        StubGraph(error=RuntimeError("secret internal detail")),
    )

    response = client.post(
        "/generate-plan",
        json={"registration_no": "24BAI1127", "mode": "day_with_timings"},
    )

    assert response.status_code == 500
    assert "secret internal detail" not in response.text


def test_empty_plan_is_a_valid_200(client, monkeypatch):
    monkeypatch.setattr(
        api_main,
        "graph",
        StubGraph(
            result={
                "study_plan": StudyPlanResponse(
                    mode=PlanMode.DAY_WITHOUT_TIMINGS, plan=[]
                )
            }
        ),
    )

    response = client.post(
        "/generate-plan",
        json={"registration_no": "24BAI1127", "mode": "day_without_timings"},
    )

    assert response.status_code == 200
    assert response.json()["plan"] == []


# ---------------- Phase 3: fast task endpoint ----------------


def test_tasks_endpoint_returns_sorted_tasks(client, monkeypatch):
    from models.task import Task
    from models.timetable import Lecture

    def fake_load(reg_no):
        return (
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
                    subject="Far",
                    task_type="Quiz",
                    platform="LMS",
                    deadline="30 December 2026",
                    work="later",
                    days_remaining=40,
                ),
                Task(
                    subject="Urgent",
                    task_type="Assignment",
                    platform="LMS",
                    deadline="02 August 2026",
                    work="now",
                    days_remaining=1,
                ),
            ],
        )

    monkeypatch.setattr(api_main, "load_academic_data", fake_load)

    body = client.get("/students/24BAI1127/tasks").json()

    assert [t["subject"] for t in body["tasks"]] == ["Urgent", "Far"]
    assert body["tasks"][0]["priority"] == "High"
    assert body["tasks"][1]["priority"] == "Low"
    assert len(body["lectures"]) == 1


def test_tasks_endpoint_unknown_student_404(client, monkeypatch):
    def boom(reg_no):
        raise StudentNotFoundError("No documents for 'NOPE'.")

    monkeypatch.setattr(api_main, "load_academic_data", boom)

    assert client.get("/students/NOPE/tasks").status_code == 404


def test_tasks_endpoint_llm_down_503(client, monkeypatch):
    def boom(reg_no):
        raise LLMOutputError("LLM service error: refused")

    monkeypatch.setattr(api_main, "load_academic_data", boom)

    assert client.get("/students/X/tasks").status_code == 503


def test_refresh_endpoint(client, monkeypatch):
    monkeypatch.setattr(api_main, "cache_clear", lambda ns: 3)

    body = client.post("/students/24BAI1127/refresh").json()

    assert body == {"cleared": 3}
