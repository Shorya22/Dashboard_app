"""Pydantic request/response models for auth endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    # 8-char floor and a letter+digit rule keeps the endpoint from being a
    # dictionary-attack magnet without imposing an enterprise-grade policy
    # the UI hasn't been designed for (no rotation, no complexity meter).
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _password_must_have_letter_and_digit(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one letter and one number")
        return value


class RegisterResponse(BaseModel):
    id: str
    email: str


class AccessTokenResponse(BaseModel):
    """Returned by login/refresh. The refresh token is never included —
    it only ever travels as an httpOnly Secure cookie."""

    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class LogoutResponse(BaseModel):
    detail: str = "Logged out"


class CurrentUser(BaseModel):
    id: str
    email: str
    role: str
