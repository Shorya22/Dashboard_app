"""
Rate limiter, shared across the app.

Lightweight in-process limiter (slowapi, keyed by client IP) — no Redis
or external infra needed for local dev. Applied specifically to
`/api/auth/login` (brute-force protection); other routes are unlimited.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
