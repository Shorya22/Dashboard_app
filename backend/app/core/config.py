"""
Application configuration.

Phase 2 added app metadata + logging config. Phase 3 adds auth/JWT/DB
settings, all overridable via environment variables so nothing sensitive
is hardcoded for a real deploy later.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=ENV_PATH)


class Settings:
    app_name: str = "Dashboard App API"
    api_v1_prefix: str = os.environ.get("API_V1_PREFIX", "/api/v1")
    log_level: int = logging.INFO

    # --- Runtime / HTTP ---
    host: str = os.environ.get("HOST", "127.0.0.1")
    port: int = int(os.environ.get("PORT", "8000"))
    frontend_url: str = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    api_base_url: str = os.environ.get("API_BASE_URL", "/api")

    # --- Auth / JWT ---
    # Local-dev default secret. MUST be overridden via the JWT_SECRET_KEY
    # env var for any real deployment — this default is intentionally
    # obvious so it's never mistaken for a production secret.
    jwt_secret_key: str = os.environ.get(
        "JWT_SECRET_KEY", "dev-only-insecure-secret-change-me"
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = int(
        os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )
    refresh_token_expire_days: int = int(
        os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )
    refresh_cookie_name: str = "refresh_token"
    # Secure=True requires HTTPS. Local dev over plain http://localhost
    # needs this off, or browsers silently drop the cookie. Flip via env
    # once served over TLS.
    cookie_secure: bool = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

    # --- Database ---
    database_url: str = os.environ.get(
        "DATABASE_URL", "sqlite:///./app/data/app.db"
    )

    # --- Dev seed user (local dev only) ---
    seed_admin_email: str = os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com")
    seed_admin_password: str = os.environ.get("SEED_ADMIN_PASSWORD", "devpassword123")


settings = Settings()


def configure_logging() -> None:
    """Configure root logging once, at app startup."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
