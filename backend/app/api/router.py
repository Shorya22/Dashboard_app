"""Aggregates all v1 routers under `/api/v1`."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.booking import router as booking_router
from app.api.config import router as config_router
from app.api.data_upload import router as data_upload_router
from app.api.roster import router as roster_router
from app.api.utilization import router as utilization_router

api_v1_router = APIRouter()
api_v1_router.include_router(roster_router)
api_v1_router.include_router(booking_router)
api_v1_router.include_router(utilization_router)
api_v1_router.include_router(data_upload_router)
api_v1_router.include_router(config_router)
