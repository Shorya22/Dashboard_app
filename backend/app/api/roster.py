"""Routes over the roster (`HR MASTER`) aggregations.

Thin per api-conventions SKILL.md: parse request, call services/, return
a typed response model. No pandas here — `data_loader.get_roster_df()`
is the only source of the DataFrame.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import demo_overrides  # TEMPORARY demo branch only — see module docstring
from app.core.security import get_current_user
from app.db.models import User
from app.models.roster import (
    EmployeeDirectoryResponse,
    RosterAttritionDetail,
    RosterBreakdowns,
    RosterSkills,
    RosterSummary,
    RosterTrends,
)
from app.services import roster_metrics
from app.services.data_loader import get_roster_df

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/roster", tags=["roster"])


@router.get("/summary", response_model=RosterSummary)
def roster_summary(user: User = Depends(get_current_user)) -> RosterSummary:
    try:
        df = get_roster_df()
        summary = RosterSummary(
            active_employees=roster_metrics.get_active_employees(df),
            inactive_employees=roster_metrics.get_inactive_employees(df),
            total_employees=roster_metrics.get_total_employees(df),
            active_pct=roster_metrics.get_active_pct(df),
            attrition_pct=roster_metrics.get_attrition_pct(df),
            voluntary_leavers=roster_metrics.get_voluntary_leavers(df),
            involuntary_leavers=roster_metrics.get_involuntary_leavers(df),
            gcc_employees=roster_metrics.get_gcc_employees(df),
            non_gcc_employees=roster_metrics.get_non_gcc_employees(df),
            average_experience_yrs=roster_metrics.get_average_experience_yrs(df),
            average_hexaware_experience=roster_metrics.get_average_hexaware_experience(df),
            pending_mapping_count=roster_metrics.get_pending_mapping_count(df),
            # period_month left unset (full-range default); wiring a filter
            # query param through to these is future filter-UI work (Phase 5).
            closing_headcount=roster_metrics.get_closing_headcount(df),
            opening_headcount=roster_metrics.get_opening_headcount(df),
            joiners=roster_metrics.get_joiners(df),
            exits=roster_metrics.get_exits(df),
            clients_covered=roster_metrics.get_clients_covered(df),
            projects=roster_metrics.get_projects(df),
            senior_lead_employees=roster_metrics.get_senior_lead_employees(df),
            departments=roster_metrics.get_departments(df),
            skills_covered=roster_metrics.get_skills_covered(df),
        )
        return demo_overrides.apply_summary(summary)
    except Exception:
        logger.exception("roster_summary: failed to compute roster summary")
        raise HTTPException(status_code=500, detail="Failed to compute roster summary")


@router.get("/breakdowns", response_model=RosterBreakdowns)
def roster_breakdowns(user: User = Depends(get_current_user)) -> RosterBreakdowns:
    try:
        df = get_roster_df()
        breakdowns = RosterBreakdowns(
            strategic_pool=roster_metrics.get_strategic_pool(df),
            workforce_category_split=roster_metrics.get_workforce_category_split(df),
            status_split=roster_metrics.get_status_split(df),
            workforce_by_type=roster_metrics.get_workforce_by_type(df),
            headcount_by_region=roster_metrics.get_headcount_by_region(df),
            workforce_by_working_entity=roster_metrics.get_workforce_by_working_entity(df),
            headcount_by_seniority=roster_metrics.get_headcount_by_seniority(df),
            workforce_by_experience_band=roster_metrics.get_workforce_by_experience_band(df),
            workforce_by_seniority_category=roster_metrics.get_workforce_by_seniority_category(
                df
            ),
        )
        return demo_overrides.apply_breakdowns(breakdowns)
    except Exception:
        logger.exception("roster_breakdowns: failed to compute roster breakdowns")
        raise HTTPException(status_code=500, detail="Failed to compute roster breakdowns")


@router.get("/trends", response_model=RosterTrends)
def roster_trends(user: User = Depends(get_current_user)) -> RosterTrends:
    try:
        df = get_roster_df()
        trends = RosterTrends(
            month_wise_closing_headcount=roster_metrics.get_month_wise_closing_headcount(df),
            monthly_joiners_vs_leavers=roster_metrics.get_monthly_joiners_vs_leavers(df),
        )
        return demo_overrides.apply_trends(trends)
    except Exception:
        logger.exception("roster_trends: failed to compute roster trends")
        raise HTTPException(status_code=500, detail="Failed to compute roster trends")


@router.get("/attrition-detail", response_model=RosterAttritionDetail)
def roster_attrition_detail(user: User = Depends(get_current_user)) -> RosterAttritionDetail:
    try:
        df = get_roster_df()
        detail = RosterAttritionDetail(
            month_wise_resignation=roster_metrics.get_month_wise_resignation(df),
            voluntary_involuntary_split=roster_metrics.get_voluntary_involuntary_split(df),
            exits_table=roster_metrics.get_exits_table(df),
        )
        return demo_overrides.apply_attrition_detail(detail)
    except Exception:
        logger.exception("roster_attrition_detail: failed to compute attrition detail")
        raise HTTPException(status_code=500, detail="Failed to compute attrition detail")


@router.get("/skills", response_model=RosterSkills)
def roster_skills(user: User = Depends(get_current_user)) -> RosterSkills:
    try:
        df = get_roster_df()
        return RosterSkills(
            skill_bifurcation_by_experience_band=(
                roster_metrics.get_skill_bifurcation_by_experience_band(df)
            ),
            skill_bifurcation_by_seniority_category=(
                roster_metrics.get_skill_bifurcation_by_seniority_category(df)
            ),
            skill_bifurcation_by_region=roster_metrics.get_skill_bifurcation_by_region(df),
            workforce_details_by_region=roster_metrics.get_workforce_details_by_region(df),
        )
    except Exception:
        logger.exception("roster_skills: failed to compute roster skills")
        raise HTTPException(status_code=500, detail="Failed to compute roster skills")


@router.get("/employees", response_model=EmployeeDirectoryResponse)
def roster_employees(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
) -> EmployeeDirectoryResponse:
    try:
        df = get_roster_df()
        records = roster_metrics.get_employee_directory(df)
        page = records[offset : offset + limit]
        return EmployeeDirectoryResponse(items=page, total=len(records))
    except Exception:
        logger.exception("roster_employees: failed to compute employee directory")
        raise HTTPException(status_code=500, detail="Failed to compute employee directory")
