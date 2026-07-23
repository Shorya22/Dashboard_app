"""Response models for utilization (`Sheet1` + `UtilizationLongTable`) endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UtilizationSummary(BaseModel):
    """Utilization Home page KPI strip."""

    total_employees: int = Field(..., description="`Total Employeess` measure (sic, typo in real DAX)")
    total_hours: float = Field(..., description="`Total Hours` measure")
    client_hours: float = Field(..., description="`Client Hours` measure")
    internal_hours: float = Field(..., description="`Internal Hours` measure")
    total_projects: int = Field(..., description="`Total Projects` measure")


class WeeklyHoursPoint(BaseModel):
    week_start: str
    client_hours: float
    internal_hours: float


class WeeklyHoursTrend(BaseModel):
    items: list[WeeklyHoursPoint]


class RegionHours(BaseModel):
    region: str
    total_hours: float


class HoursByRegion(BaseModel):
    items: list[RegionHours]


class RegionMarketHours(BaseModel):
    """Region + Market (EC) combined breakdown.

    Not a confirmed named DAX measure (see data-model SKILL.md) — the
    real `Market (EC)` values are `Technology`, `BN`, `DACH`, `UKI`, not
    the `AMER`/`BENO`/`DACH`/`UKI` labels some reference screenshots use.
    Exposed as-is; do not remap.
    """

    region: str
    market: str
    total_hours: float


class HoursByRegionMarket(BaseModel):
    items: list[RegionMarketHours]


class WeekHierarchyEntry(BaseModel):
    """One week placed in its Year > Month > Week bucket, so the utilization
    filter bar can cascade Year -> Month -> Week. `month` is the booking
    sheet's own `Month` label (e.g. "May 26") — authoritative over deriving
    it from the week's Monday, since the business assigns some boundary weeks
    to the adjacent month."""

    year: str
    month: str
    week: str


class FilterOptions(BaseModel):
    weeks: list[str]
    # Year > Month > Week nesting for the cascading date filter. `weeks`
    # above is kept as the flat list (still used where no cascade is needed).
    week_hierarchy: list[WeekHierarchyEntry]
    regions: list[str]
    markets: list[str]
    departments: list[str]
    entities: list[str]
    holdings: list[str]
    hours_types: list[str]


class HoldingProjects(BaseModel):
    holding: str
    projects: list[str]


class HoldingsProjectsResponse(BaseModel):
    items: list[HoldingProjects]


class BookingRecord(BaseModel):
    week_start: str | None = None
    date: str | None = None
    employee: str | None = None
    project: str | None = None
    holding: str | None = None
    hours_type: str | None = None
    hours: float = 0.0
    region: str | None = None
    department: str | None = None
    team: str | None = None


class RecordsSummary(BaseModel):
    total_hours: float
    client_hours: float
    internal_hours: float
    total_projects: int
    average_hours: float


class RecordsResponse(BaseModel):
    items: list[BookingRecord]
    total: int
    summary: RecordsSummary


class HoursByProject(BaseModel):
    project: str
    total_hours: float


class HoursByEmployee(BaseModel):
    employee: str
    client_hours: float
    internal_hours: float


class EmployeeUtilizationDetail(BaseModel):
    employee: str
    total_hours: float
    client_hours: float
    internal_hours: float
    total_projects: int
    hours_by_project: list[HoursByProject]
    hours_by_week: list[WeeklyHoursPoint]


class ProjectDetailRow(BaseModel):
    employee: str | None = None
    project: str | None = None
    region: str | None = None
    department: str | None = None


class ProjectUtilizationDetail(BaseModel):
    holding: str
    total_hours: float
    client_hours: float
    internal_hours: float
    hours_by_employee: list[HoursByEmployee]
    hours_by_week: list[WeeklyHoursPoint]
    detail: list[ProjectDetailRow]


class WeeklyUtilizationTrendPoint(BaseModel):
    week_start: str
    avg_weekly_utilization_pct: float


class UtilizationSplit(BaseModel):
    high: int
    moderate: int
    low: int


class EmployeeUtilizationRanking(BaseModel):
    employee: str
    period_utilization_pct: float


class UtilizationOverview(BaseModel):
    average_period_utilization_pct: float = Field(
        ..., description="`Average Period Utilization %` measure, 0-1"
    )
    total_employees: int
    latest_week_utilization_pct: float = Field(
        ..., description="`Latest Week Utilization %` measure, 0-1"
    )
    weekly_trend: list[WeeklyUtilizationTrendPoint]
    utilization_split: UtilizationSplit
    employee_ranking: list[EmployeeUtilizationRanking]
