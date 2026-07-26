"""
QA (quality-assurance) endpoints — admin-only tooling that compares
runtime dashboard aggregations against alternative sources of truth.

Currently exposes one route: reconcile Formula A (booking-derived
`Weekly Utilization %`) against the ground-truth `Utilization_Long`
sheet, which as of 2026-07-26 is NO LONGER a runtime dependency (Overview
moved to booking-derived Formula A per METRICS.md Page 8). The
ground-truth workbook survives only as a QA input consumed here.

Behaviour:
- Admin-only via `require_role("admin")`, matching data-upload routes.
- Ground truth is lazy-loaded via `data_loader.get_utilization_ground_truth_df`.
- If the file is absent (loader returns None) the route returns 404 with a
  helpful body naming where the file is expected.
- Otherwise it returns the full reconciliation result dict from
  `utilization_metrics.reconcile_weekly_utilization` (matched/mismatched
  counts, Formula A match rate, mismatch list, unmatched employee/weeks).

The 10/152 residual mismatches documented in the utilization_metrics
top-of-file docstring are still present here — this endpoint is exactly
where the divergence between Formula A and the ground truth's shipped
values is meant to surface.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import require_role
from app.db.models import User
from app.services import utilization_metrics
from app.services.data_loader import (
    get_booking_df_prepared,
    get_utilization_ground_truth_df,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["qa"])

require_admin = require_role("admin")


@router.get("/reconcile")
def qa_reconcile(
    dataset: str = Query("utilization", description="Which reconciliation to run — only 'utilization' is implemented today."),
    user: User = Depends(require_admin),
) -> dict:
    """
    Reconcile booking-derived Formula A against the ground-truth
    `Utilization_Long` sheet, employee/week by employee/week.

    Returns the full result dict from
    `utilization_metrics.reconcile_weekly_utilization`:

      {
        "matched_employee_weeks": int,
        "formula_a_exact_matches": int,
        "formula_b_exact_matches": int,
        "formula_a_match_rate": float,   # 0-1
        "formula_b_match_rate": float,
        "mismatches": [...],
        "unmatched_ground_truth_employee_weeks": [...],
      }

    404 if the ground-truth file is not present under `backend/data/`
    (or as an uploaded version) — the file is optional at runtime and
    only this QA path requires it.
    """
    if dataset != "utilization":
        raise HTTPException(
            status_code=404,
            detail=f"Unknown reconcile dataset {dataset!r}. Valid: 'utilization'",
        )
    gt = get_utilization_ground_truth_df()
    if gt is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Ground-truth file not found. This QA endpoint compares the "
                "runtime booking-derived Formula A against "
                "`PowerBI_Ready_Utilization_May_2026.xlsx` (sheet "
                "`Utilization_Long`). Place the file under `backend/data/` "
                "(or upload it via the admin data-upload flow) and retry. "
                "The dashboard's Overview page does not need this file — "
                "only this reconcile endpoint does."
            ),
        )
    try:
        booking = get_booking_df_prepared()
        return utilization_metrics.reconcile_weekly_utilization(booking, gt)
    except Exception:
        logger.exception("qa_reconcile: reconciliation failed")
        raise HTTPException(status_code=500, detail="Reconciliation failed")
