"""Pydantic request/response models for auth endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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
