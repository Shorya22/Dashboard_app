"""Microsoft Entra ID SSO (OIDC, Authorization Code flow) via MSAL.

Kept in services/ per project convention — routes stay thin and never
touch MSAL or persistence directly.

The `state`-keyed pending-flow store below is an in-memory dict. That's
correct for this app's current single-process `uvicorn` dev setup, but
would silently break behind multiple worker processes or replicas (a
login started on one process could complete on another, with no shared
state). Flagged here rather than baked in silently — swap for a shared
store (Redis, DB-backed) before running with more than one process.
"""

from __future__ import annotations

import logging
import secrets
import time

import msal
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import User, UserRole

logger = logging.getLogger(__name__)

_SCOPES = ["User.Read"]
_FLOW_TTL_SECONDS = 600  # generous for a login-redirect round trip

# state -> (flow dict, created_at)
_pending_flows: dict[str, tuple[dict, float]] = {}


class SsoError(Exception):
    """Raised for any failure starting or completing the SSO flow."""


def _msal_app() -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        client_id=settings.azure_client_id,
        client_credential=settings.azure_client_secret,
        authority=settings.azure_authority,
    )


def _prune_expired_flows() -> None:
    cutoff = time.time() - _FLOW_TTL_SECONDS
    expired = [s for s, (_, ts) in _pending_flows.items() if ts < cutoff]
    for s in expired:
        _pending_flows.pop(s, None)


def build_auth_redirect() -> str:
    """Starts the login flow and returns the Microsoft auth URL to
    redirect the browser to. The flow (incl. state + PKCE verifier) is
    stashed server-side, keyed by its own `state`, for the callback."""
    if not settings.sso_configured:
        raise SsoError("SSO is not configured (missing Azure tenant/client settings)")

    app = _msal_app()
    flow = app.initiate_auth_code_flow(_SCOPES, redirect_uri=settings.azure_redirect_uri)
    _prune_expired_flows()
    _pending_flows[flow["state"]] = (flow, time.time())
    return flow["auth_uri"]


def complete_auth_flow(query_params: dict) -> dict:
    """Exchanges the callback's query params for validated ID token claims.

    Raises SsoError on any failure: unknown/expired/replayed state, or
    Microsoft rejecting the code exchange.
    """
    state = query_params.get("state")
    pending = _pending_flows.pop(state, None) if state else None
    if pending is None:
        raise SsoError("Unknown or expired login attempt — please try signing in again")
    flow, _ = pending

    result = _msal_app().acquire_token_by_auth_code_flow(flow, query_params)
    if "error" in result:
        raise SsoError(result.get("error_description") or result["error"])

    claims = result.get("id_token_claims")
    if not claims:
        raise SsoError("Microsoft did not return an ID token")
    return claims


def get_or_create_sso_user(db: Session, claims: dict) -> User:
    """Looks up a user by Azure's `oid` claim first (a stable per-user
    identifier), falling back to email — so an existing local-password
    account gets linked on first Microsoft login instead of duplicated.
    Creates a new viewer-role user if neither matches.

    The created/linked user's `hashed_password` is a hash of a random
    value nobody knows, not a real password — password login for this
    account will simply always fail bcrypt verification, which is the
    intended behavior for an SSO-only account.
    """
    external_id = claims.get("oid") or claims.get("sub")
    email = (claims.get("preferred_username") or claims.get("email") or "").strip().lower()
    if not email:
        raise SsoError("Microsoft did not return an email/preferred_username claim")

    user = db.query(User).filter(User.external_id == external_id).first() if external_id else None
    if user is None:
        user = db.query(User).filter(User.email == email).first()

    if user is None:
        user = User(
            email=email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            role=UserRole.viewer,
            auth_provider="microsoft",
            external_id=external_id,
        )
        db.add(user)
        logger.info("get_or_create_sso_user: created new SSO user email=%s", email)
    elif user.auth_provider != "microsoft" or user.external_id != external_id:
        user.auth_provider = "microsoft"
        user.external_id = external_id
        logger.info("get_or_create_sso_user: linked existing user_id=%s to SSO", user.id)

    db.commit()
    db.refresh(user)
    return user
