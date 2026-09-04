"""Registration, login and logout.

These credentials belong to CampusSync AI only. We never ask for, receive or
store a university password.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from api.deps import current_student
from api.rate_limit import login_limiter, reset_limiter
from config import get_logger
from db.models import Student
from db.repository import (
    DuplicateStudentError,
    authenticate,
    create_student,
    reset_password_with_code,
)
from db.security import PasswordError, create_session, destroy_session
from db.session import get_session

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    registration_no: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    registration_no: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    token: str
    registration_no: str
    name: str = ""
    # Present only in the sign-up response. Shown once, never retrievable.
    recovery_code: str = ""


class ResetRequest(BaseModel):
    registration_no: str = Field(min_length=1, max_length=32)
    recovery_code: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=6, max_length=128)


class ResetResponse(BaseModel):
    recovery_code: str


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(request: RegisterRequest, session: Session = Depends(get_session)):
    try:
        student, recovery_code = create_student(
            session,
            registration_no=request.registration_no.strip(),
            password=request.password,
            name=request.name.strip(),
        )

    except DuplicateStudentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    except PasswordError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return AuthResponse(
        token=create_session(student.id),
        registration_no=student.registration_no,
        name=student.name,
        recovery_code=recovery_code,
    )


@router.post("/reset-password", response_model=ResetResponse)
def reset_password(
    request: ResetRequest, session: Session = Depends(get_session)
):
    """Set a new password using the one-time recovery code.

    Deliberately does not reveal whether the account exists: a wrong
    registration number and a wrong code produce the same error, so this
    cannot be used to enumerate who has an account.
    """
    key = request.registration_no.strip().lower()
    allowed, retry_after = reset_limiter.check(key)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many reset attempts. Please wait before trying again.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        replacement = reset_password_with_code(
            session,
            registration_no=request.registration_no.strip(),
            recovery_code=request.recovery_code,
            new_password=request.new_password,
        )
    except PasswordError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if replacement is None:
        raise HTTPException(
            status_code=401,
            detail="That registration number and recovery code do not match.",
        )

    return ResetResponse(recovery_code=replacement)


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest, session: Session = Depends(get_session)):
    key = request.registration_no.strip().lower()
    allowed, retry_after = login_limiter.check(key)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many sign-in attempts. Please wait a few minutes.",
            headers={"Retry-After": str(retry_after)},
        )

    student = authenticate(
        session, request.registration_no.strip(), request.password
    )

    if student is None:
        # Deliberately does not reveal whether the account exists.
        raise HTTPException(
            status_code=401, detail="Incorrect registration number or password."
        )

    return AuthResponse(
        token=create_session(student.id),
        registration_no=student.registration_no,
        name=student.name,
    )


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    if authorization:
        _, _, token = authorization.partition(" ")
        destroy_session(token)

    return {"status": "logged out"}


@router.get("/me", response_model=AuthResponse)
def me(student: Student = Depends(current_student)):
    return AuthResponse(
        token="",
        registration_no=student.registration_no,
        name=student.name,
    )
