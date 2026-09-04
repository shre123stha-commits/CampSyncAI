"""Microsoft Teams adapter.

The behaviour that matters most is the admin-consent fallback: every
EduAssignments permission requires tenant admin approval, so a student in an
unapproved tenant must still get their deadlines from the calendar rather
than seeing the source fail.
"""

import pytest
from sources import teams_source
from sources.base import SourceError
from sources.teams_source import (
    PermissionDenied,
    TeamsSource,
    _parse_due,
    authorization_url,
)

# --- Dates ----------------------------------------------------------------


def test_parses_graph_utc_timestamp():
    assert _parse_due("2026-09-15T23:59:00Z") == "15 September 2026"


def test_parses_offset_timestamp():
    assert _parse_due("2026-09-15T23:59:00+05:30") == "15 September 2026"


def test_unparseable_date_is_empty_not_an_error():
    assert _parse_due("next tuesday") == ""
    assert _parse_due(None) == ""
    assert _parse_due("") == ""


# --- Authorization URL ----------------------------------------------------


def test_authorization_url_requests_offline_access(monkeypatch):
    """Without offline_access Microsoft never issues a refresh token."""
    monkeypatch.setattr(teams_source, "MS_CLIENT_ID", "abc")
    monkeypatch.setattr(teams_source, "MS_TENANT", "common")

    url = authorization_url("state123")

    assert "offline_access" in url
    assert "state123" in url
    assert "prompt=consent" in url
    assert url.startswith("https://login.microsoftonline.com/common/")


# --- The admin-consent fallback ------------------------------------------


def test_falls_back_to_calendar_when_assignments_are_denied(monkeypatch):
    """403 on education scopes must not fail the source."""
    from models.task import Task

    monkeypatch.setattr(
        teams_source, "access_token_from", lambda token: "access"
    )

    def denied(token):
        raise PermissionDenied("/education/me/classes")

    calendar_task = Task(
        subject="Maths lecture",
        task_type="Assignment",
        platform="Teams",
        deadline="15 September 2026",
        work="Problem set",
    )

    monkeypatch.setattr(teams_source, "fetch_education_assignments", denied)
    monkeypatch.setattr(
        teams_source, "fetch_calendar_deadlines", lambda token: [calendar_task]
    )

    _, tasks = TeamsSource().fetch({"refresh_token": "rt"})

    assert tasks == [calendar_task]


def test_uses_assignments_when_they_are_permitted(monkeypatch):
    """With admin consent the direct route is preferred."""
    from models.task import Task

    assignment = Task(
        subject="Physics",
        task_type="Assignment",
        platform="Teams",
        deadline="20 September 2026",
        work="Lab report",
    )

    monkeypatch.setattr(
        teams_source, "access_token_from", lambda token: "access"
    )
    monkeypatch.setattr(
        teams_source, "fetch_education_assignments", lambda token: [assignment]
    )

    def should_not_run(token):
        raise AssertionError("calendar fallback must not be used")

    monkeypatch.setattr(teams_source, "fetch_calendar_deadlines", should_not_run)

    _, tasks = TeamsSource().fetch({"refresh_token": "rt"})

    assert tasks == [assignment]


def test_both_denied_explains_admin_consent(monkeypatch):
    """The student must learn it is an IT decision, not their mistake."""
    monkeypatch.setattr(
        teams_source, "access_token_from", lambda token: "access"
    )

    def denied(token):
        raise PermissionDenied("/x")

    monkeypatch.setattr(teams_source, "fetch_education_assignments", denied)
    monkeypatch.setattr(teams_source, "fetch_calendar_deadlines", denied)

    with pytest.raises(SourceError) as exc:
        TeamsSource().fetch({"refresh_token": "rt"})

    assert "administrator" in str(exc.value).lower()


def test_missing_token_is_a_clear_error():
    with pytest.raises(SourceError) as exc:
        TeamsSource().fetch({})

    assert "not connected" in str(exc.value).lower()


# --- Parsing Graph payloads ----------------------------------------------


def test_draft_assignments_are_skipped(monkeypatch):
    """Drafts are not yet visible to students."""
    calls = {"n": 0}

    def fake_get(path, token, params=None):
        calls["n"] += 1
        if path == "/education/me/classes":
            return {"value": [{"id": "c1", "displayName": "Maths"}]}
        return {
            "value": [
                {"displayName": "Draft work", "status": "draft"},
                {
                    "displayName": "Real assignment",
                    "status": "assigned",
                    "dueDateTime": {"dateTime": "2026-09-15T23:59:00Z"},
                },
            ]
        }

    monkeypatch.setattr(teams_source, "_get", fake_get)

    tasks = teams_source.fetch_education_assignments("token")

    assert len(tasks) == 1
    assert tasks[0].work == "Real assignment"
    assert tasks[0].deadline == "15 September 2026"
    assert tasks[0].subject == "Maths"
    assert tasks[0].platform == "Teams"


def test_calendar_events_without_a_title_are_skipped(monkeypatch):
    def fake_get(path, token, params=None):
        return {
            "value": [
                {"subject": "", "start": {"dateTime": "2026-09-15T10:00:00Z"}},
                {
                    "subject": "Chemistry quiz",
                    "start": {"dateTime": "2026-09-16T10:00:00Z"},
                    "bodyPreview": "Covers chapters 1-3",
                },
            ]
        }

    monkeypatch.setattr(teams_source, "_get", fake_get)

    tasks = teams_source.fetch_calendar_deadlines("token")

    assert len(tasks) == 1
    assert tasks[0].subject == "Chemistry quiz"
    assert tasks[0].task_type == "Quiz"


def test_registry_exposes_teams():
    from db.models import SourceType
    from sources.registry import ADAPTERS, _config_for

    assert SourceType.TEAMS in ADAPTERS
    assert _config_for(SourceType.TEAMS, "secret") == {"refresh_token": "secret"}
