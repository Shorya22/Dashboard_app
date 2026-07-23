"""Routes over the utilization portal's 6 pages — booking-sheet aggregations
(`Sheet1`) and the ground-truth `%`-based measures (`UtilizationLongTable`).

Thin per api-conventions SKILL.md: no pandas here, all aggregation lives in
`services/booking_metrics.py` / `services/utilization_metrics.py`.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.db.models import User
from app.models.utilization import (
    BookingRecord,
    EmployeeUtilizationDetail,
    FilterOptions,
    HoldingProjects,
    HoldingsProjectsResponse,
    HoursByRegion,
    HoursByRegionMarket,
    ProjectUtilizationDetail,
    RecordsResponse,
    RecordsSummary,
    RegionHours,
    RegionMarketHours,
    UtilizationOverview,
    UtilizationSummary,
    WeeklyHoursPoint,
    WeeklyHoursTrend,
)
from app.services import booking_metrics, utilization_metrics
from app.services.data_loader import (
    get_booking_df,
    get_booking_df_prepared,
    get_roster_df,
    get_utilization_ground_truth_df,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/utilization", tags=["utilization"])


# Shared filter-param dependency for every utilization endpoint whose
# chart / KPI is drawn alongside the Utilization Home / Search filter
# row. Previously only `/records` accepted filters, so the KPI cards
# (`/summary`), Weekly Hours Trend (`/weekly-trend`) and both region
# breakdowns (`/by-region`, `/by-region-market`) rendered off unfiltered
# data — the Total Hours by Market/Region chart in particular stayed
# identical no matter which region the user picked, a real user-visible
# bug. Same repeated-query-param shape as `/records`, applied via
# `booking_metrics.get_filtered_records` so filter semantics (OR within
# a field, AND across fields, blank -> no-op) can never diverge between
# routes.
def _booking_filter_params(
    week: list[str] | None = Query(None),
    region: list[str] | None = Query(None),
    market: list[str] | None = Query(None),
    department: list[str] | None = Query(None),
    entity: list[str] | None = Query(None),
    holding: list[str] | None = Query(None),
    hours_type: list[str] | None = Query(None),
) -> dict[str, list[str] | None]:
    return {
        "week": week,
        "region": region,
        "market": market,
        "department": department,
        "entity": entity,
        "holding": holding,
        "hours_type": hours_type,
    }


def _apply_booking_filters(filters: dict[str, list[str] | None]) -> "pd.DataFrame":  # type: ignore[name-defined]
    """Load the prepared booking df and narrow it by the shared filter params."""
    df = get_booking_df_prepared()
    return booking_metrics.get_filtered_records(df, **filters)


@router.get("/summary", response_model=UtilizationSummary)
def utilization_summary(
    user: User = Depends(get_current_user),
    filters: dict = Depends(_booking_filter_params),
) -> UtilizationSummary:
    try:
        df = _apply_booking_filters(filters)
        return UtilizationSummary(
            total_employees=booking_metrics.get_total_employees(df),
            total_hours=booking_metrics.get_total_hours(df),
            client_hours=booking_metrics.get_client_hours(df),
            internal_hours=booking_metrics.get_internal_hours(df),
            total_projects=booking_metrics.get_total_projects(df),
        )
    except Exception:
        logger.exception("utilization_summary: failed to compute utilization summary")
        raise HTTPException(status_code=500, detail="Failed to compute utilization summary")


@router.get("/weekly-trend", response_model=WeeklyHoursTrend)
def utilization_weekly_trend(
    user: User = Depends(get_current_user),
    filters: dict = Depends(_booking_filter_params),
) -> WeeklyHoursTrend:
    try:
        df = _apply_booking_filters(filters)
        items = [WeeklyHoursPoint(**row) for row in booking_metrics.get_weekly_hours_trend(df)]
        return WeeklyHoursTrend(items=items)
    except Exception:
        logger.exception("utilization_weekly_trend: failed to compute weekly hours trend")
        raise HTTPException(status_code=500, detail="Failed to compute weekly hours trend")


@router.get("/by-region", response_model=HoursByRegion)
def utilization_by_region(
    user: User = Depends(get_current_user),
    filters: dict = Depends(_booking_filter_params),
) -> HoursByRegion:
    try:
        df = _apply_booking_filters(filters)
        items = [RegionHours(**row) for row in booking_metrics.get_hours_by_region(df)]
        return HoursByRegion(items=items)
    except Exception:
        logger.exception("utilization_by_region: failed to compute hours by region")
        raise HTTPException(status_code=500, detail="Failed to compute hours by region")


@router.get("/by-region-market", response_model=HoursByRegionMarket)
def utilization_by_region_market(
    user: User = Depends(get_current_user),
    filters: dict = Depends(_booking_filter_params),
) -> HoursByRegionMarket:
    """Region + Market (EC) hours breakdown, filter-aware.

    Not a confirmed named DAX measure — see data-model SKILL.md and
    `services/booking_metrics.get_hours_by_region_market` docstring for
    the Market (EC) label caveat (real values are Technology/BN/DACH/UKI,
    not AMER/BENO/DACH/UKI). Applies the same filter param set as every
    other utilization endpoint so this chart reacts to the filter row
    just like the KPIs and Weekly Hours Trend beside it.
    """
    try:
        df = _apply_booking_filters(filters)
        items = [RegionMarketHours(**row) for row in booking_metrics.get_hours_by_region_market(df)]
        return HoursByRegionMarket(items=items)
    except Exception:
        logger.exception("utilization_by_region_market: failed to compute hours by region+market")
        raise HTTPException(status_code=500, detail="Failed to compute hours by region and market")


@router.get("/filter-options", response_model=FilterOptions)
def utilization_filter_options(user: User = Depends(get_current_user)) -> FilterOptions:
    try:
        df = get_booking_df()
        # Roster is passed so the Utilization Home Region/Market filter can
        # union booking's `Region (EC)`/`Market (EC)` with the roster's
        # master `Region`/`Market` taxonomy — see
        # booking_metrics.get_filter_options for rationale.
        roster_df = get_roster_df()
        return FilterOptions(**booking_metrics.get_filter_options(df, roster_df))
    except Exception:
        logger.exception("utilization_filter_options: failed to compute filter options")
        raise HTTPException(status_code=500, detail="Failed to compute filter options")


@router.get("/records", response_model=RecordsResponse)
def utilization_records(
    week: list[str] | None = Query(None),
    region: list[str] | None = Query(None),
    market: list[str] | None = Query(None),
    department: list[str] | None = Query(None),
    entity: list[str] | None = Query(None),
    holding: list[str] | None = Query(None),
    hours_type: list[str] | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
) -> RecordsResponse:
    """
    Filter params each accept a single value or multiple repeated query
    params (e.g. `?region=EMEA&region=AMER`) — OR within a field, AND
    across fields. See `booking_metrics.get_filtered_records` docstring.
    """
    try:
        df = get_booking_df_prepared()
        filtered = booking_metrics.get_filtered_records(
            df,
            week=week,
            region=region,
            market=market,
            department=department,
            entity=entity,
            holding=holding,
            hours_type=hours_type,
        )
        summary = RecordsSummary(**booking_metrics.get_records_summary(filtered))
        page = filtered.iloc[offset : offset + limit]
        items = [BookingRecord(**row) for row in booking_metrics.records_to_dicts(page)]
        return RecordsResponse(items=items, total=len(filtered), summary=summary)
    except Exception:
        logger.exception("utilization_records: failed to compute filtered records")
        raise HTTPException(status_code=500, detail="Failed to compute filtered records")


@router.get("/employees/{employee}", response_model=EmployeeUtilizationDetail)
def utilization_employee_detail(
    employee: str, user: User = Depends(get_current_user)
) -> EmployeeUtilizationDetail:
    try:
        df = get_booking_df()
        detail = booking_metrics.get_employee_detail(df, employee)
    except Exception:
        logger.exception("utilization_employee_detail: failed to compute employee detail")
        raise HTTPException(status_code=500, detail="Failed to compute employee detail")
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No booking records found for employee '{employee}'")
    return EmployeeUtilizationDetail(
        employee=detail["employee"],
        total_hours=detail["total_hours"],
        client_hours=detail["client_hours"],
        internal_hours=detail["internal_hours"],
        total_projects=detail["total_projects"],
        hours_by_project=[dict(item) for item in detail["hours_by_project"]],
        hours_by_week=[dict(item) for item in detail["hours_by_week"]],
    )


@router.get("/projects/{holding}", response_model=ProjectUtilizationDetail)
def utilization_project_detail(
    holding: str, user: User = Depends(get_current_user)
) -> ProjectUtilizationDetail:
    try:
        df = get_booking_df()
        detail = booking_metrics.get_project_detail(df, holding)
    except Exception:
        logger.exception("utilization_project_detail: failed to compute project detail")
        raise HTTPException(status_code=500, detail="Failed to compute project detail")
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No booking records found for holding '{holding}'")
    return ProjectUtilizationDetail(**detail)


@router.get("/holdings-projects", response_model=HoldingsProjectsResponse)
def utilization_holdings_projects(user: User = Depends(get_current_user)) -> HoldingsProjectsResponse:
    """
    Static holding -> distinct project-name hierarchy, for populating the
    Search page's filter dropdown without fetching every booking record
    client-side. See `booking_metrics.get_holdings_with_projects`.
    """
    try:
        df = get_booking_df()
        items = [
            HoldingProjects(**row) for row in booking_metrics.get_holdings_with_projects(df)
        ]
        return HoldingsProjectsResponse(items=items)
    except Exception:
        logger.exception("utilization_holdings_projects: failed to compute holdings/projects")
        raise HTTPException(status_code=500, detail="Failed to compute holdings/projects")


@router.get("/overview", response_model=UtilizationOverview)
def utilization_overview(user: User = Depends(get_current_user)) -> UtilizationOverview:
    try:
        df = get_utilization_ground_truth_df()
        return UtilizationOverview(**utilization_metrics.get_utilization_overview(df))
    except Exception:
        logger.exception("utilization_overview: failed to compute utilization overview")
        raise HTTPException(status_code=500, detail="Failed to compute utilization overview")
