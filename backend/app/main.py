"""
FastAPI application entrypoint.

Phase 2 scope: skeleton app, /health, and /api/v1/roster+booking summary
endpoints wired to Phase-1 services/ functions. No auth yet (Phase 3).
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from contextvars import ContextVar
from pathlib import Path

# Support running this file as a script from the backend directory:
#   python app/main.py
# without requiring PYTHONPATH or `python -m app.main`.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import anyio.to_thread
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.router import api_v1_router
from app.core.config import configure_logging, settings
from app.core.limiter import limiter
from app.db.session import Base, SessionLocal, engine
from app.services.user_service import seed_dev_admin_if_empty

configure_logging()
logger = logging.getLogger(__name__)

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


# Attach request_id to every log line without requiring every logger call
# to pass it explicitly.
_request_id_formatter = logging.Formatter(
    "%(asctime)s %(levelname)s [%(name)s] [req=%(request_id)s] %(message)s"
)
for handler in logging.getLogger().handlers:
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(_request_id_formatter)

app = FastAPI(title=settings.app_name)
app.state.limiter = limiter
# Cheap, safe win for JSON payloads (e.g. /roster/employees,
# /utilization/records with large limits) — only compresses responses
# above the default 500-byte minimum, so small responses are untouched.
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # Keep the standard {"detail": ...} error shape rather than slowapi's default body.
    return JSONResponse(status_code=429, content={"detail": "Too many login attempts. Try again later."})


@app.on_event("startup")
def _startup_create_db_and_seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_dev_admin_if_empty(db)
    finally:
        db.close()


@app.on_event("startup")
async def _startup_raise_thread_limit() -> None:
    # Every route handler in this app is a plain `def` (not `async def`) by
    # design — see api-conventions SKILL.md — so Starlette runs all of them
    # in anyio's worker thread pool, whose default cap is 40. Under 100
    # concurrent requests that cap would queue the 41st+ request behind
    # threads freed by earlier ones, adding latency that has nothing to do
    # with the actual (fast, in-memory) work each request does. Raise the
    # ceiling once at startup so concurrent load maps ~1:1 to worker threads
    # instead of queuing.
    anyio.to_thread.current_default_thread_limiter().total_tokens = 100


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    token = request_id_ctx.set(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s status=%s duration_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        if request.method == "GET" and request.url.path.startswith(settings.api_v1_prefix):
            # Read-only dashboard aggregations backed by the in-memory,
            # rarely-reloaded DataFrames in data_loader.py — short TTL lets
            # the browser skip a redundant round-trip on back/forward nav
            # within a session without risking noticeably stale data.
            response.headers["Cache-Control"] = "private, max-age=60"
        return response
    finally:
        request_id_ctx.reset(token)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak raw exception details to the client.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health_router)
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
# Auth lives at /api/auth/... (not /api/v1/...) per api-conventions SKILL.md.
app.include_router(auth_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
