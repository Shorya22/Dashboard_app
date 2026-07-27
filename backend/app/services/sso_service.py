"""Microsoft Entra ID SSO (OIDC, Authorization Code flow) via MSAL.

Kept in services/ per project convention — routes stay thin and never
touch MSAL or persistence directly.

The pending-flow store is the `sso_flows` DB table (see app.db.models),
not an in-memory dict — deliberately, so the login-start request and the
callback request can land on different app instances/replicas (an
in-memory dict only works for a single process, which would silently
break under Azure App Service/Container Apps autoscaling).
"""

from __future__ import annotations

import datetime
import json
import logging
import secrets

import msal
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import SsoFlow, User, UserRole

logger = logging.getLogger(__name__)

_SCOPES = ["User.Read"]
_FLOW_TTL = datetime.timedelta(seconds=600)  # generous for a login-redirect round trip


class SsoError(Exception):
    """Raised for any failure starting or completing the SSO flow."""


def _msal_app() -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        client_id=settings.azure_client_id,
        client_credential=settings.azure_client_secret,
        authority=settings.azure_authority,
    )


def _prune_expired_flows(db: Session) -> None:
    cutoff = datetime.datetime.now(datetime.timezone.utc) - _FLOW_TTL
    db.query(SsoFlow).filter(SsoFlow.created_at < cutoff).delete()


def build_auth_redirect(db: Session) -> str:
    """Starts the login flow and returns the Microsoft auth URL to
    redirect the browser to. The flow (incl. state + PKCE verifier) is
    stashed in `sso_flows`, keyed by its own `state`, for the callback —
    any app instance can complete it, not just the one that started it."""
    if not settings.sso_configured:
        raise SsoError("SSO is not configured (missing Azure tenant/client settings)")

    app = _msal_app()
    flow = app.initiate_auth_code_flow(_SCOPES, redirect_uri=settings.azure_redirect_uri)
    _prune_expired_flows(db)
    db.add(SsoFlow(state=flow["state"], flow_json=json.dumps(flow)))
    db.commit()
    return flow["auth_uri"]


def complete_auth_flow(db: Session, query_params: dict) -> dict:
    """Exchanges the callback's query params for validated ID token claims.

    Raises SsoError on any failure: unknown/expired/replayed state, or
    Microsoft rejecting the code exchange.
    """
    state = query_params.get("state")
    row = db.get(SsoFlow, state) if state else None
    if row is None:
        raise SsoError("Unknown or expired login attempt — please try signing in again")

    # One-time use: delete immediately so a replayed callback can't reuse it.
    db.delete(row)
    db.commit()

    # SQLite hands back a naive datetime even for a DateTime(timezone=True)
    # column (unlike Postgres, which preserves tzinfo) — normalize to UTC
    # before comparing so this works correctly on both.
    created_at = row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=datetime.timezone.utc)
    if created_at < datetime.datetime.now(datetime.timezone.utc) - _FLOW_TTL:
        raise SsoError("Login attempt expired — please try signing in again")

    flow = json.loads(row.flow_json)
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
