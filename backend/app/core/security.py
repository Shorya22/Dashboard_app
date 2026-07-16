"""
Auth logic: password hashing and JWT issuing/validation.

Per api-conventions SKILL.md, all of this lives here (not scattered
across route files):
- Access token: short-lived (~15 min), returned in the login JSON body.
- Refresh token: longer-lived, set as an httpOnly Secure cookie only —
  never returned in JSON, never stored in localStorage.
- `get_current_user` is the single dependency every protected route uses
  to validate the access token from the `Authorization: Bearer ...`
  header.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Literal

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import User
from app.db.session import get_db

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_bearer_scheme = HTTPBearer(auto_error=False)

TokenType = Literal["access", "refresh"]


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, role: str, token_type: TokenType, expires_delta: datetime.timedelta) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user: User) -> str:
    return _create_token(
        subject=user.id,
        role=user.role.value,
        token_type="access",
        expires_delta=datetime.timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user: User) -> str:
    return _create_token(
        subject=user.id,
        role=user.role.value,
        token_type="refresh",
        expires_delta=datetime.timedelta(days=settings.refresh_token_expire_days),
    )


class TokenError(Exception):
    """Raised for any invalid/expired/wrong-type token."""


def decode_token(token: str, expected_type: TokenType) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid token") from exc

    if payload.get("type") != expected_type:
        raise TokenError(f"Expected {expected_type} token")
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Shared dependency for every protected route.

    Validates the access token from the Authorization: Bearer header.
    Raises 401 with the standard `{"detail": ...}` shape on any failure
    (missing header, malformed token, expired token, wrong token type,
    or user no longer exists) — never leaks internals.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or not credentials.credentials:
        raise unauthorized

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenError as exc:
        logger.info("get_current_user: rejected token (%s)", exc)
        raise unauthorized from exc

    user = db.get(User, payload.get("sub"))
    if user is None:
        raise unauthorized

    return user


def require_role(*roles: str):
    """Optional role-gate helper, layered on top of get_current_user.

    Not applied anywhere yet (no role-restricted routes exist in this
    phase), but provided since the `role` field is meant to be usable
    from the start per the requirements.
    """

    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role.value not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _dependency
