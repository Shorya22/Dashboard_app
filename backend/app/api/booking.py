"""Routes over the booking (`Sheet1`) aggregations.

Thin per api-conventions SKILL.md: no pandas here, no utilization-%
endpoints (still blocked per data-model skill — no overlapping week
between the booking sheet and the ground-truth sheet yet).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.db.models import User
from app.models.booking import BookingSummary
from app.services import booking_metrics
from app.services.data_loader import get_booking_df

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/booking", tags=["booking"])


@router.get("/summary", response_model=BookingSummary)
def booking_summary(user: User = Depends(get_current_user)) -> BookingSummary:
    try:
        df = get_booking_df()
        return BookingSummary(
            total_hours=booking_metrics.get_total_hours(df),
            hours_split=booking_metrics.get_hours_split(df),
            client_hours=booking_metrics.get_client_hours(df),
            internal_hours=booking_metrics.get_internal_hours(df),
            client_hours_pct=booking_metrics.get_client_hours_pct(df),
            internal_hours_pct=booking_metrics.get_internal_hours_pct(df),
            total_clients=booking_metrics.get_total_clients(df),
            total_projects=booking_metrics.get_total_projects(df),
            total_regions=booking_metrics.get_total_regions(df),
            markets_covered=booking_metrics.get_markets_covered(df),
        )
    except Exception:
        logger.exception("booking_summary: failed to compute booking summary")
        raise HTTPException(status_code=500, detail="Failed to compute booking summary")
