"""HTTP client for the CampusSync AI backend."""

from __future__ import annotations

import os

import requests

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

TIMEOUT = int(os.getenv("BACKEND_TIMEOUT", "180"))


class BackendError(Exception):
    """A user-presentable backend failure."""


def _request(method: str, path: str, **kwargs):
    url = f"{BASE_URL}{path}"

    try:
        response = requests.request(method, url, timeout=TIMEOUT, **kwargs)

    except requests.exceptions.ConnectionError as exc:
        raise BackendError(
            "Cannot reach the CampusSync AI backend. "
            f"Is it running at {BASE_URL}?"
        ) from exc

    except requests.exceptions.Timeout as exc:
        raise BackendError(
            "The backend took too long to respond. The AI model may still be "
            "loading — please try again."
        ) from exc

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = None

        if isinstance(detail, list) and detail:
            detail = detail[0].get("msg", str(detail))

        raise BackendError(detail or f"Backend error {response.status_code}.")

    return response.json()


def generate_plan(student_id: str, mode: str) -> dict:
    """Request a study plan. Raises BackendError on failure."""
    return _request(
        "POST",
        "/generate-plan",
        json={"registration_no": student_id, "mode": mode},
    )


def get_tasks(student_id: str) -> dict:
    """Fetch tasks + timetable without running the planner.

    Served from the backend's extraction cache when warm, so this is fast.
    """
    return _request("GET", f"/students/{student_id}/tasks")


def refresh_student(student_id: str) -> dict:
    """Invalidate the backend's cached extraction for this student."""
    return _request("POST", f"/students/{student_id}/refresh")


def list_students() -> list[str]:
    try:
        return _request("GET", "/students").get("students", [])
    except BackendError:
        return []


def backend_online() -> bool:
    try:
        _request("GET", "/health")
        return True
    except BackendError:
        return False
