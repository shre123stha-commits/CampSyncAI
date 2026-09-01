"""HTTP client for the CampusSync AI backend."""

from __future__ import annotations

import os

import requests

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

TIMEOUT = int(os.getenv("BACKEND_TIMEOUT", "180"))


class BackendError(Exception):
    """A user-presentable backend failure."""


class AuthError(BackendError):
    """The session is missing or has expired."""


def _request(method: str, path: str, token: str | None = None, **kwargs):
    url = f"{BASE_URL}{path}"

    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.request(
            method, url, timeout=TIMEOUT, headers=headers, **kwargs
        )

    except requests.exceptions.ConnectionError as exc:
        raise BackendError(
            f"Cannot reach the CampusSync AI backend. Is it running at "
            f"{BASE_URL}?"
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

        message = detail or f"Backend error {response.status_code}."

        if response.status_code == 401:
            raise AuthError(message)

        raise BackendError(message)

    return response.json()


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


def register(registration_no: str, password: str, name: str = "") -> dict:
    return _request(
        "POST",
        "/auth/register",
        json={
            "registration_no": registration_no,
            "password": password,
            "name": name,
        },
    )


def login(registration_no: str, password: str) -> dict:
    return _request(
        "POST",
        "/auth/login",
        json={"registration_no": registration_no, "password": password},
    )


def logout(token: str) -> None:
    try:
        _request("POST", "/auth/logout", token=token)
    except BackendError:
        pass


# --------------------------------------------------------------------------
# Tasks
# --------------------------------------------------------------------------


def get_tasks(token: str, include_completed: bool = True) -> dict:
    return _request(
        "GET",
        f"/tasks?include_completed={str(include_completed).lower()}",
        token=token,
    )


def set_task_completed(token: str, task_id: int, completed: bool) -> dict:
    return _request(
        "PATCH", f"/tasks/{task_id}", token=token, json={"completed": completed}
    )


def refresh_data(token: str) -> dict:
    return _request("POST", "/refresh", token=token)


def upload_document(token: str, kind: str, filename: str, data: bytes) -> dict:
    return _request(
        "POST",
        f"/upload?kind={kind}",
        token=token,
        files={"file": (filename, data, "application/octet-stream")},
    )


# --------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------


def generate_my_plan(token: str, mode: str) -> dict:
    return _request(
        "POST", "/my/generate-plan", token=token, json={"mode": mode}
    )


def backend_online() -> bool:
    try:
        _request("GET", "/health")
        return True
    except BackendError:
        return False
