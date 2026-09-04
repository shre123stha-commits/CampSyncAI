"""Source connection endpoints, end to end against a real in-memory DB."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import agents.academic_agent as academic
import api.main as api_main
import db.models  # noqa: F401
import sources.registry as registry
from db.crypto import decrypt
from db.models import SourceConnection, SourceType
from db.security import clear_sessions
import db.session as db_session
from db.session import get_session
from models.task import Task
from sources.base import SourceError


@pytest.fixture
def ctx(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    # Code that opens its own session (session persistence) must use the
    # test engine too, not the real database file.
    db_session.set_engine(engine)

    def override():
        with Session(engine) as session:
            yield session

    api_main.app.dependency_overrides[get_session] = override
    clear_sessions()

    monkeypatch.setattr(
        academic, "load_academic_data", lambda reg: ([], [])
    )
    import api.routes_tasks as routes_tasks

    monkeypatch.setattr(
        routes_tasks, "load_academic_data", academic.load_academic_data
    )

    with TestClient(api_main.app, raise_server_exceptions=False) as client:
        yield client, engine

    api_main.app.dependency_overrides.clear()


def token_for(client, reg="24BAI1127"):
    response = client.post(
        "/auth/register",
        json={"registration_no": reg, "password": "hunter22"},
    )
    return response.json()["token"]


def head(token):
    return {"Authorization": f"Bearer {token}"}


ICS_TASK = Task(
    subject="Ethics",
    task_type="Assignment",
    platform="Calendar",
    deadline="12 October 2026",
    work="Write the essay",
)


# ---------------- listing ----------------


def test_sources_requires_auth(ctx):
    client, _ = ctx
    assert client.get("/sources").status_code == 401


def test_lists_all_sources(ctx):
    client, _ = ctx
    token = token_for(client)

    body = client.get("/sources", headers=head(token)).json()
    types = {s["type"] for s in body["sources"]}

    assert types == {"document", "ics", "classroom", "teams"}
    assert all(s["connected"] is False for s in body["sources"])


def test_teams_marked_unavailable_without_config(ctx, monkeypatch):
    """Teams must self-disable rather than offering a button that 503s."""
    client, _ = ctx
    token = token_for(client)

    body = client.get("/sources", headers=head(token)).json()
    teams = next(s for s in body["sources"] if s["type"] == "teams")

    assert teams["available"] is False


def test_teams_authorize_requires_configuration(ctx):
    client, _ = ctx
    token = token_for(client)

    response = client.get("/sources/teams/authorize", headers=head(token))

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"].lower()


def test_classroom_marked_unavailable_without_config(ctx, monkeypatch):
    client, _ = ctx
    import api.routes_sources as routes_sources

    monkeypatch.setattr(routes_sources, "classroom_configured", lambda: False)

    token = token_for(client)
    body = client.get("/sources", headers=head(token)).json()

    classroom = next(s for s in body["sources"] if s["type"] == "classroom")
    assert classroom["available"] is False


# ---------------- ICS connect ----------------


def test_connect_ics(ctx, monkeypatch):
    client, engine = ctx
    import api.routes_sources as routes_sources

    monkeypatch.setattr(
        routes_sources.ICSSource,
        "fetch",
        lambda self, config: ([], [ICS_TASK]),
    )

    token = token_for(client)

    response = client.post(
        "/sources/ics",
        json={"url": "https://x.edu/feed.ics"},
        headers=head(token),
    )

    assert response.status_code == 200
    assert response.json()["tasks_found"] == 1


def test_connected_url_is_encrypted_at_rest(ctx, monkeypatch):
    client, engine = ctx
    import api.routes_sources as routes_sources

    monkeypatch.setattr(
        routes_sources.ICSSource, "fetch", lambda self, config: ([], [])
    )

    token = token_for(client)
    url = "https://x.edu/private-feed.ics"

    client.post("/sources/ics", json={"url": url}, headers=head(token))

    with Session(engine) as session:
        connection = session.query(SourceConnection).first()

    assert url not in connection.secret, "URL must not be stored in plaintext"
    assert decrypt(connection.secret) == url


def test_bad_ics_url_rejected(ctx):
    client, _ = ctx
    token = token_for(client)

    response = client.post(
        "/sources/ics", json={"url": "not-a-url"}, headers=head(token)
    )

    assert response.status_code == 422


def test_unreachable_feed_reported(ctx, monkeypatch):
    client, _ = ctx
    import api.routes_sources as routes_sources

    def boom(self, config):
        raise SourceError("The calendar feed was not found (404).")

    monkeypatch.setattr(routes_sources.ICSSource, "fetch", boom)

    token = token_for(client)

    response = client.post(
        "/sources/ics",
        json={"url": "https://x.edu/missing.ics"},
        headers=head(token),
    )

    assert response.status_code == 422
    assert "404" in response.json()["detail"]


def test_reconnecting_replaces_the_connection(ctx, monkeypatch):
    client, engine = ctx
    import api.routes_sources as routes_sources

    monkeypatch.setattr(
        routes_sources.ICSSource, "fetch", lambda self, config: ([], [])
    )

    token = token_for(client)

    client.post(
        "/sources/ics", json={"url": "https://x.edu/a.ics"}, headers=head(token)
    )
    client.post(
        "/sources/ics", json={"url": "https://x.edu/b.ics"}, headers=head(token)
    )

    with Session(engine) as session:
        connections = session.query(SourceConnection).all()

    assert len(connections) == 1
    assert decrypt(connections[0].secret) == "https://x.edu/b.ics"


# ---------------- disconnect ----------------


def test_disconnect_removes_the_secret(ctx, monkeypatch):
    client, engine = ctx
    import api.routes_sources as routes_sources

    monkeypatch.setattr(
        routes_sources.ICSSource, "fetch", lambda self, config: ([], [])
    )

    token = token_for(client)
    client.post(
        "/sources/ics", json={"url": "https://x.edu/a.ics"}, headers=head(token)
    )

    response = client.delete("/sources/ics", headers=head(token))

    assert response.status_code == 200

    with Session(engine) as session:
        assert session.query(SourceConnection).count() == 0


def test_disconnect_unconnected_source_404(ctx):
    client, _ = ctx
    token = token_for(client)

    assert client.delete("/sources/ics", headers=head(token)).status_code == 404


def test_students_cannot_see_each_others_connections(ctx, monkeypatch):
    client, _ = ctx
    import api.routes_sources as routes_sources

    monkeypatch.setattr(
        routes_sources.ICSSource, "fetch", lambda self, config: ([], [])
    )

    token_a = token_for(client, "24BAI1127")
    client.post(
        "/sources/ics", json={"url": "https://x.edu/a.ics"}, headers=head(token_a)
    )

    token_b = token_for(client, "24BCS1028")
    body = client.get("/sources", headers=head(token_b)).json()

    assert all(s["connected"] is False for s in body["sources"])


# ---------------- OAuth guards ----------------


def test_classroom_authorize_requires_config(ctx, monkeypatch):
    client, _ = ctx
    import api.routes_sources as routes_sources

    monkeypatch.setattr(routes_sources, "classroom_configured", lambda: False)

    token = token_for(client)

    response = client.get("/sources/classroom/authorize", headers=head(token))

    assert response.status_code == 503


def test_callback_rejects_unknown_state(ctx):
    client, _ = ctx

    response = client.get(
        "/sources/classroom/callback?code=abc&state=forged"
    )

    assert response.status_code == 200
    assert "Invalid or expired" in response.text


def test_callback_reports_user_denial(ctx):
    client, _ = ctx

    response = client.get(
        "/sources/classroom/callback?error=access_denied&state=x"
    )

    assert "cancelled" in response.text.lower()


# ---------------- tasks integration ----------------


def test_connected_source_contributes_tasks(ctx, monkeypatch):
    client, _ = ctx

    monkeypatch.setattr(
        registry,
        "fetch_connected_tasks",
        lambda session, student_id: ([ICS_TASK], []),
    )
    import api.routes_tasks as routes_tasks

    monkeypatch.setattr(
        routes_tasks, "fetch_connected_tasks", registry.fetch_connected_tasks
    )

    token = token_for(client)
    body = client.get("/tasks", headers=head(token)).json()

    assert body["stats"]["total"] == 1
    assert body["tasks"][0]["subject"] == "Ethics"


def test_failing_source_does_not_break_the_request(ctx, monkeypatch):
    """A broken feed must degrade gracefully, not 500."""
    client, _ = ctx

    import api.routes_tasks as routes_tasks

    monkeypatch.setattr(
        routes_tasks,
        "fetch_connected_tasks",
        lambda session, student_id: (
            [ICS_TASK],
            ["Google Classroom: token expired."],
        ),
    )

    token = token_for(client)
    response = client.get("/tasks", headers=head(token))

    assert response.status_code == 200

    body = response.json()
    assert body["stats"]["total"] == 1, "Working sources still contribute"
    assert body["source_errors"] == ["Google Classroom: token expired."]


def test_llm_down_does_not_block_other_sources(ctx, monkeypatch):
    """Regression: Ollama being unavailable must not 503 the dashboard when
    a calendar feed is working."""
    client, _ = ctx

    import api.routes_tasks as routes_tasks
    from utils.llm_json import LLMOutputError

    def boom(reg_no):
        raise LLMOutputError("LLM service error: connection refused")

    monkeypatch.setattr(routes_tasks, "load_academic_data", boom)
    monkeypatch.setattr(
        routes_tasks,
        "fetch_connected_tasks",
        lambda session, student_id: ([ICS_TASK], []),
    )

    token = token_for(client)
    response = client.get("/tasks", headers=head(token))

    assert response.status_code == 200, "Must degrade, not fail"

    body = response.json()
    assert body["stats"]["total"] == 1
    assert any("AI service" in e for e in body["source_errors"])


def test_llm_down_with_no_other_sources_still_returns_200(ctx, monkeypatch):
    client, _ = ctx

    import api.routes_tasks as routes_tasks
    from utils.llm_json import LLMOutputError

    def boom(reg_no):
        raise LLMOutputError("LLM service error: connection refused")

    monkeypatch.setattr(routes_tasks, "load_academic_data", boom)
    monkeypatch.setattr(
        routes_tasks, "fetch_connected_tasks", lambda s, i: ([], [])
    )

    token = token_for(client)
    response = client.get("/tasks", headers=head(token))

    assert response.status_code == 200
    assert response.json()["stats"]["total"] == 0
