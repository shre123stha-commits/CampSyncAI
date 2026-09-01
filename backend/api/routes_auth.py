"""Registration, login and logout.

These credentials belong to CampusSync AI only. We never ask for, receive or
store a university password.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from api.deps import current_student
from config import get_logger
from db.models import Student
from db.repository import (
    DuplicateStudentError,
    authenticate,
    create_student,
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


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(request: RegisterRequest, session: Session = Depends(get_session)):
    try:
        student = create_student(
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
    )


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest, session: Session = Depends(get_session)):
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
