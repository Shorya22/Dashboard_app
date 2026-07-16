"""Response models for roster (`HR MASTER`) endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

PROVISIONAL_EXPERIENCE_BAND_NOTE = (
    "PROVISIONAL — bucket boundaries for `Experience Band` are a "
    "best-effort guess, not confirmed against the real DAX calculated "
    "column. See data-model skill."
)
PROVISIONAL_SENIORITY_CATEGORY_NOTE = (
    "PROVISIONAL — mapping for `Seniority Category` is a best-effort "
    "guess, not confirmed against the real DAX calculated column. See "
    "data-model skill."
)


class RosterSummary(BaseModel):
    active_employees: int = Field(..., description="`Active Employees` measure")
    inactive_employees: int = Field(..., description="`Inactive Employees` measure")
    total_employees: int = Field(..., description="`Total Employees` measure")
    active_pct: float = Field(..., description="`Active %` measure")
    attrition_pct: float = Field(
        ..., description="`Attrition %` measure (PROVISIONAL, see data-model skill)"
    )
    voluntary_leavers: int = Field(..., description="`Voluntary Leavers` measure")
    involuntary_leavers: int = Field(..., description="`InVoluntary Leavers` measure")
    gcc_employees: int = Field(..., description="`GCC Employees` measure")
    non_gcc_employees: int = Field(..., description="`Non GCC Employees` measure")
    average_experience_yrs: float = Field(
        ..., description="`Average Experience (Yrs)` measure"
    )
    average_hexaware_experience: float = Field(
        ..., description="`Average Hexaware Experience` measure"
    )
    pending_mapping_count: int = Field(
        ...,
        description=(
            "`Pending Mapping Count` measure (PROVISIONAL, unvalidated "
            "against real DAX, see data-model skill)"
        ),
    )
    closing_headcount: int = Field(
        ...,
        description=(
            "`Closing Headcount` measure, full-range default (documented "
            "~2-person gap vs the Power BI reference due to unresolved "
            "`DOJ (DEPT)` = 'TBD' rows, see data-model skill)"
        ),
    )
    opening_headcount: int = Field(
        ...,
        description=(
            "`Opening Headcount` measure, full-range default (0 under the "
            "full-range default is expected/documented, see data-model skill)"
        ),
    )
    joiners: int = Field(..., description="`Joiners` measure, full-range default")
    exits: int = Field(..., description="`Exits` measure, full-range default")
    clients_covered: int = Field(
        ...,
        description=(
            "`Clients Covered` measure — DISTINCTCOUNT of raw "
            "`Client as on June 2026` string values, excluding blanks and "
            "'Client TBD'"
        ),
    )
    projects: int = Field(
        ...,
        description=(
            "`Projects` measure — DISTINCTCOUNT of `Client as on June 2026`, "
            "intentionally the same column as Clients Covered per the real "
            "DAX (copy-paste artifact, see data-model skill)"
        ),
    )
    senior_lead_employees: int = Field(
        ..., description="`Senior - Lead Employees` measure"
    )
    departments: int = Field(
        ..., description="`Departments` measure — DISTINCTCOUNT of `Designation`"
    )
    skills_covered: int = Field(
        ...,
        description=(
            "`Skills Covered` measure — DISTINCTCOUNT of `Skill` "
            "(NOT `Primary Skill`), excluding blank and 'TBD'-containing values"
        ),
    )


# --------------------------------------------------------------------------
# Breakdowns (GET /api/v1/roster/breakdowns)
# --------------------------------------------------------------------------


class RosterBreakdowns(BaseModel):
    strategic_pool: int = Field(..., description="`Strategic Pool` measure")
    workforce_category_split: dict[str, int] = Field(
        ...,
        description=(
            "Active vs Strategic Pool. NOTE: these two figures are not "
            "guaranteed mutually exclusive/exhaustive — see "
            "get_workforce_category_split docstring in roster_metrics.py"
        ),
    )
    status_split: dict[str, int] = Field(..., description="Active vs Inactive, full roster")
    workforce_by_type: dict[str, int] = Field(..., description="GCC vs Non GCC, full roster")
    headcount_by_region: dict[str, int] = Field(
        ..., description="Distinct employee count per `Region`, full roster"
    )
    workforce_by_working_entity: dict[str, int] = Field(
        ..., description="Distinct employee count per `Working Entity`, full roster"
    )
    headcount_by_seniority: dict[str, int] = Field(
        ...,
        description=(
            "Distinct employee count per RAW `Seniorirty Level` value "
            "(includes casing duplicates and 'Seniority TBD' as-is)"
        ),
    )
    workforce_by_experience_band: dict[str, int] = Field(
        ..., description=PROVISIONAL_EXPERIENCE_BAND_NOTE
    )
    workforce_by_seniority_category: dict[str, int] = Field(
        ..., description=PROVISIONAL_SENIORITY_CATEGORY_NOTE
    )


# --------------------------------------------------------------------------
# Trends (GET /api/v1/roster/trends)
# --------------------------------------------------------------------------


class MonthClosingHeadcount(BaseModel):
    month: str = Field(..., description="Month label, e.g. 'Jul 2025'")
    closing_headcount: int = Field(..., description="`Closing Headcount` measure for this month")


class MonthJoinersVsLeavers(BaseModel):
    month: str = Field(..., description="Month label, e.g. 'Jul 2025'")
    joiners: int = Field(..., description="`Joiners` measure for this month")
    exits: int = Field(..., description="`Exits` measure for this month")


class RosterTrends(BaseModel):
    month_wise_closing_headcount: list[MonthClosingHeadcount]
    monthly_joiners_vs_leavers: list[MonthJoinersVsLeavers]


# --------------------------------------------------------------------------
# Attrition detail (GET /api/v1/roster/attrition-detail)
# --------------------------------------------------------------------------


class MonthResignation(BaseModel):
    month: str = Field(..., description="Month label, e.g. 'Jul 2025'")
    exits: int = Field(..., description="`Exits` measure for this month")


class ExitRecord(BaseModel):
    name: str | None = None
    designation: str | None = None
    primary_skill: str | None = None
    region: str | None = None
    market: str | None = None
    type: str | None = None
    lwd: str | None = Field(None, description="Raw source `LWD` string, unparsed")
    reason_for_leaving: str | None = None
    status: str | None = None


class RosterAttritionDetail(BaseModel):
    month_wise_resignation: list[MonthResignation]
    voluntary_involuntary_split: dict[str, int]
    exits_table: list[ExitRecord]


# --------------------------------------------------------------------------
# Skills (GET /api/v1/roster/skills)
# --------------------------------------------------------------------------


class SkillByExperienceBand(BaseModel):
    primary_skill: str
    experience_band: str = Field(..., description=PROVISIONAL_EXPERIENCE_BAND_NOTE)
    count: int


class SkillBySeniorityCategory(BaseModel):
    primary_skill: str
    seniority_category: str = Field(..., description=PROVISIONAL_SENIORITY_CATEGORY_NOTE)
    count: int


class SkillByRegion(BaseModel):
    primary_skill: str
    region: str
    count: int


class WorkforceDetailByRegion(BaseModel):
    region: str
    seniority_category: str = Field(..., description=PROVISIONAL_SENIORITY_CATEGORY_NOTE)
    count: int


class RosterSkills(BaseModel):
    skill_bifurcation_by_experience_band: list[SkillByExperienceBand]
    skill_bifurcation_by_seniority_category: list[SkillBySeniorityCategory]
    skill_bifurcation_by_region: list[SkillByRegion]
    workforce_details_by_region: list[WorkforceDetailByRegion] = Field(
        ...,
        description=(
            "AMBIGUOUS chart content — provisionally Region x Seniority "
            "Category, unconfirmed against the reference PDF. See "
            "get_workforce_details_by_region docstring in roster_metrics.py"
        ),
    )


# --------------------------------------------------------------------------
# Employee directory (GET /api/v1/roster/employees) — paginated
# --------------------------------------------------------------------------


class EmployeeRecord(BaseModel):
    employee_id: str | int | None = Field(..., description="`NEW_EMP_ID`")
    name: str | None = None
    grade: str | None = None
    designation: str | None = None
    work_location: str | None = None
    total_experience: float | None = None
    working_entity: str | None = None
    client: str | None = Field(
        None, description="Raw `Client as on June 2026`, may be multi-value comma-separated"
    )
    seniority_level: str | None = Field(None, description="Raw `Seniorirty Level` source value")
    region: str | None = None
    market: str | None = None
    status: str | None = None
    type: str | None = None
    primary_skill: str | None = None
    skill: str | None = Field(
        None, description="Raw `Skill` source value (broader grouping than `Primary Skill`)"
    )
    supervisor: str | None = None


class EmployeeDirectoryResponse(BaseModel):
    items: list[EmployeeRecord]
    total: int
