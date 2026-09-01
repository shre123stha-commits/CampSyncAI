import pytest

from sources.base import SourceError
from sources.ics_source import (
    ICSSource,
    infer_subject,
    infer_task_type,
    normalise_url,
    parse_calendar,
    validate_url,
)


def build_ics(*events: str) -> bytes:
    body = "\n".join(events)
    return (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Test//EN\n"
        f"{body}\nEND:VCALENDAR"
    ).encode()


EVENT = """BEGIN:VEVENT
UID:1
SUMMARY:Machine Learning - Assignment 3 is due
DTSTART;VALUE=DATE:20260910
DESCRIPTION:Build a decision tree classifier.
END:VEVENT"""


# ---------------- URL handling ----------------


def test_webcal_is_normalised():
    assert normalise_url("webcal://x.edu/f.ics") == "https://x.edu/f.ics"


def test_whitespace_stripped():
    assert normalise_url("  https://x.edu/f.ics  ") == "https://x.edu/f.ics"


def test_empty_url_rejected():
    with pytest.raises(SourceError):
        validate_url("")


def test_non_http_scheme_rejected():
    with pytest.raises(SourceError):
        validate_url("ftp://x.edu/f.ics")


def test_valid_url_passes():
    assert validate_url("https://x.edu/f.ics") == "https://x.edu/f.ics"


# ---------------- inference ----------------


@pytest.mark.parametrize(
    "summary,expected",
    [
        ("Quiz 2 tomorrow", "Quiz"),
        ("Final exam", "Exam"),
        ("Lab report submission", "Lab Report"),
        ("Group project milestone", "Project"),
        ("Viva voce", "Viva"),
        ("Presentation slides", "Presentation"),
        ("Assignment 1", "Assignment"),
        ("Something unlabelled", "Assignment"),
    ],
)
def test_task_type_inference(summary, expected):
    assert infer_task_type(summary) == expected


@pytest.mark.parametrize(
    "summary,expected",
    [
        ("Machine Learning - Assignment 3", "Machine Learning"),
        ("Databases: Quiz 2", "Databases"),
        ("Networks (Lab 4)", "Networks"),
        ("Plain title", "Plain title"),
    ],
)
def test_subject_inference(summary, expected):
    assert infer_subject(summary) == expected


def test_empty_summary_is_handled():
    assert infer_subject("") == "Untitled"


# ---------------- parsing ----------------


def test_parses_a_vevent():
    tasks = parse_calendar(build_ics(EVENT))

    assert len(tasks) == 1
    assert tasks[0].subject == "Machine Learning"
    assert tasks[0].deadline == "10 September 2026"
    assert tasks[0].platform == "Calendar"
    assert "decision tree" in tasks[0].work


def test_parses_a_vtodo_with_due():
    todo = """BEGIN:VTODO
UID:9
SUMMARY:Networks Lab Report
DUE;VALUE=DATE:20260908
END:VTODO"""

    tasks = parse_calendar(build_ics(todo))

    assert tasks[0].deadline == "08 September 2026"
    assert tasks[0].task_type == "Lab Report"


def test_parses_datetime_dtstart():
    event = """BEGIN:VEVENT
UID:2
SUMMARY:Databases Quiz
DTSTART:20260915T090000Z
END:VEVENT"""

    assert parse_calendar(build_ics(event))[0].deadline == "15 September 2026"


def test_events_without_a_date_are_skipped():
    event = "BEGIN:VEVENT\nUID:3\nSUMMARY:No date here\nEND:VEVENT"
    assert parse_calendar(build_ics(event)) == []


def test_events_without_a_summary_are_skipped():
    event = "BEGIN:VEVENT\nUID:4\nDTSTART;VALUE=DATE:20260910\nEND:VEVENT"
    assert parse_calendar(build_ics(event)) == []


def test_duplicate_events_are_collapsed():
    tasks = parse_calendar(build_ics(EVENT, EVENT))
    assert len(tasks) == 1


def test_empty_calendar_yields_nothing():
    assert parse_calendar(build_ics()) == []


def test_falls_back_to_summary_when_no_description():
    event = """BEGIN:VEVENT
UID:5
SUMMARY:Ethics essay
DTSTART;VALUE=DATE:20261001
END:VEVENT"""

    assert parse_calendar(build_ics(event))[0].work == "Ethics essay"


def test_garbage_input_raises_source_error():
    with pytest.raises(SourceError):
        parse_calendar(b"this is definitely not a calendar")


# ---------------- fetching ----------------


class FakeRaw:
    def __init__(self, data: bytes):
        self.data = data

    def read(self, amount, decode_content=True):
        return self.data[:amount]


class FakeResponse:
    def __init__(self, data: bytes = b"", status_code: int = 200):
        self.status_code = status_code
        self.raw = FakeRaw(data)


def test_fetch_success(monkeypatch):
    import sources.ics_source as module

    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *a, **k: FakeResponse(build_ics(EVENT)),
    )

    lectures, tasks = ICSSource().fetch({"url": "https://x.edu/f.ics"})

    assert lectures == []
    assert len(tasks) == 1


@pytest.mark.parametrize(
    "status,fragment",
    [(404, "not found"), (403, "rejected"), (401, "rejected"), (500, "error")],
)
def test_http_errors_are_friendly(monkeypatch, status, fragment):
    import sources.ics_source as module

    monkeypatch.setattr(
        module.requests, "get", lambda *a, **k: FakeResponse(b"", status)
    )

    with pytest.raises(SourceError, match=fragment):
        ICSSource().fetch({"url": "https://x.edu/f.ics"})


def test_empty_feed_raises(monkeypatch):
    import sources.ics_source as module

    monkeypatch.setattr(
        module.requests, "get", lambda *a, **k: FakeResponse(b"   ")
    )

    with pytest.raises(SourceError, match="empty"):
        ICSSource().fetch({"url": "https://x.edu/f.ics"})


def test_oversized_feed_raises(monkeypatch):
    import sources.ics_source as module

    monkeypatch.setattr(module, "MAX_FEED_BYTES", 10)
    monkeypatch.setattr(
        module.requests, "get", lambda *a, **k: FakeResponse(b"x" * 100)
    )

    with pytest.raises(SourceError, match="too large"):
        ICSSource().fetch({"url": "https://x.edu/f.ics"})


def test_timeout_is_friendly(monkeypatch):
    import sources.ics_source as module

    def boom(*args, **kwargs):
        raise module.requests.exceptions.Timeout()

    monkeypatch.setattr(module.requests, "get", boom)

    with pytest.raises(SourceError, match="timed out"):
        ICSSource().fetch({"url": "https://x.edu/f.ics"})


def test_connection_error_is_friendly(monkeypatch):
    import sources.ics_source as module

    def boom(*args, **kwargs):
        raise module.requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(module.requests, "get", boom)

    with pytest.raises(SourceError, match="Could not reach"):
        ICSSource().fetch({"url": "https://x.edu/f.ics"})
