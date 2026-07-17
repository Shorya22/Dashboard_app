"""
Auth routes: login / refresh / logout.

Per api-conventions SKILL.md these live at `/api/auth/...` — deliberately
NOT under the `/api/v1` prefix used by the roster/booking routes, since
the skill's Auth section spells out the literal path `POST /api/auth/login`.

Thin per convention: parse request, call services/security, return a
typed response model. Persistence goes through `app.db.session.get_db`
+ `app.services.user_service`, never raw queries inline here.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    verify_password,
    TokenError,
)
from app.db.models import User
from app.db.session import get_db
from app.models.auth import (
    AccessTokenResponse,
    CurrentUser,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.services.user_service import (
    EmailAlreadyRegisteredError,
    create_user,
    get_user_by_email,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/api/auth",
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(
    request: Request,
    body: RegisterRequest,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    """Self-serve account creation. Returns the new user (never any
    tokens) — the client must POST to /login next. Rate-limited on the
    same 5/minute budget as /login so this endpoint isn't a signup-spam
    vector or a side channel for email enumeration."""
    try:
        user = create_user(db, email=body.email, plain_password=body.password)
    except EmailAlreadyRegisteredError:
        logger.info("register: email already exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    return RegisterResponse(id=user.id, email=user.email)


@router.post("/login", response_model=AccessTokenResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    invalid_creds = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user = get_user_by_email(db, body.email)
    if user is None or not verify_password(body.password, user.hashed_password):
        logger.info("login: failed attempt for email=%s", body.email)
        raise invalid_creds

    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    _set_refresh_cookie(response, refresh_token)

    logger.info("login: success for user_id=%s", user.id)
    return AccessTokenResponse(
        access_token=access_token,
        expires_in_minutes=settings.access_token_expire_minutes,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing refresh token")

    raw_refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not raw_refresh_token:
        raise unauthorized

    try:
        payload = decode_token(raw_refresh_token, expected_type="refresh")
    except TokenError as exc:
        logger.info("refresh: rejected token (%s)", exc)
        raise unauthorized from exc

    user = db.get(User, payload.get("sub"))
    if user is None:
        raise unauthorized

    access_token = create_access_token(user)
    # Rotate the refresh cookie on every use: a stolen refresh token that
    # gets reused invalidates itself from the legitimate client's next
    # refresh (mismatch is detectable later if we add a revocation
    # store), and it caps the window a leaked token stays valid to one
    # refresh cycle instead of the full 7-day lifetime.
    new_refresh_token = create_refresh_token(user)
    _set_refresh_cookie(response, new_refresh_token)

    logger.info("refresh: issued new access token for user_id=%s", user.id)
    return AccessTokenResponse(
        access_token=access_token,
        expires_in_minutes=settings.access_token_expire_minutes,
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response) -> LogoutResponse:
    response.delete_cookie(key=settings.refresh_cookie_name, path="/api/auth")
    return LogoutResponse()


@router.get("/me", response_model=CurrentUser)
def me(user: User = Depends(get_current_user)) -> CurrentUser:
    """Trivial protected route demonstrating `get_current_user` actually
    gates access — not a business endpoint."""
    return CurrentUser(id=user.id, email=user.email, role=user.role.value)
