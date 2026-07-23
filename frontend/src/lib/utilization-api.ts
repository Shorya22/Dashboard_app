import { useQuery } from '@tanstack/react-query'
import { apiClient } from './api-client'
import { marketDisplayLabel } from './chart-colors'
import type { HierarchicalItem } from '@/components/dashboard/hierarchical-multi-select'

// Types mirror /api/v1/utilization/* responses (see /openapi.json). Keep
// field names exact — measure names confirmed against the running backend.

export interface UtilizationSummary {
  total_employees: number
  total_hours: number
  client_hours: number
  internal_hours: number
  total_projects: number
}

export interface WeeklyTrendPoint {
  week_start: string
  client_hours: number
  internal_hours: number
}
export interface WeeklyTrendResponse {
  items: WeeklyTrendPoint[]
}

export interface RegionHours {
  region: string
  total_hours: number
}
export interface ByRegionResponse {
  items: RegionHours[]
}

export interface RegionMarketHours {
  region: string
  market: string
  total_hours: number
}
export interface ByRegionMarketResponse {
  items: RegionMarketHours[]
}

export interface WeekHierarchyEntry {
  year: string
  month: string
  week: string
}

export interface RegionMarketOption {
  region: string
  markets: string[]
}

/** Split a hierarchical Region/Market selection into `region[]` / `market[]`
 * record-filter params: a plain value is a Region, a `"<region>::<market>"`
 * value is a Market (the market alone narrows the rows; the backend ANDs the
 * two). Undefined when nothing of that kind is selected. */
export function splitRegionMarketSelection(selected: string[]): {
  region?: string[]
  market?: string[]
} {
  const regions: string[] = []
  const markets: string[] = []
  for (const v of selected) {
    const idx = v.indexOf('::')
    if (idx === -1) regions.push(v)
    else markets.push(v.slice(idx + 2))
  }
  return {
    region: regions.length ? regions : undefined,
    market: markets.length ? markets : undefined,
  }
}

/** Canonical utilization-side Region > Market tree builder — the HR side
 * has its own (`buildRegionMarketItems` in `employee-filters.ts`) that
 * feeds off the roster employee list. One canonical helper per side.
 *
 * Build the Region > Market tree for the Utilization Home page's unified
 * Region/Market filter, from the backend's `region_market_hierarchy`
 * (unioned across roster + booking taxonomies — see
 * `booking_metrics.get_filter_options`). Region is a hierarchy-only group
 * (`isGroup: true`), so ticking a region toggles all its markets without
 * emitting the region as a filter value; Market leaves are encoded as
 * `"<region>::<market>"` so they round-trip through
 * `splitRegionMarketSelection`. Regions without any markets still appear
 * as an empty group so the user can see they exist (roster-only regions
 * — the whole point of the union). */
export function regionMarketHierarchyToItems(
  hier: RegionMarketOption[] | undefined,
): HierarchicalItem[] {
  const items: HierarchicalItem[] = []
  for (const { region, markets } of hier ?? []) {
    items.push({ value: region, label: region, isGroup: true })
    for (const market of markets) {
      items.push({
        value: `${region}::${market}`,
        label: marketDisplayLabel(market),
        parent: region,
      })
    }
  }
  return items
}

// Canonical formatters for Year>Month>Week labels — shared with the
// weeksToHierarchy() helpers in utilization-search-page.tsx and
// employee-utilization-page.tsx. Kept in sync deliberately: Month =
// "Apr 2026", Week = "13 Apr 2026". Year is just the 4-digit year.
const WEEK_MONTH_FMT = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' })
const WEEK_DAY_FMT = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

/** Build the Year > Month > Week tree for the hierarchical date multi-select
 * from the backend's `week_hierarchy`. Year and Month are hierarchy-only
 * groups (`isGroup: true`); Week is a selectable leaf whose `value` is the
 * ISO week-start Monday date (`YYYY-MM-DD`) — the filter value the API
 * expects. So ticking a Year or Month toggles all descendant weeks.
 *
 * IMPORTANT — labels are derived from the `week` field, NOT from the
 * backend's `year`/`month` strings.
 *
 * Why: the backend's `month` field comes from the booking sheet's `Month`
 * column, which is a real `datetime64` in the source file (see data-model
 * SKILL.md 2026-07-21 note); `str(month)` on the backend produces
 * `"2026-04-26 00:00:00"`, which would leak into the label as a raw
 * datetime. Deriving labels from the ISO week Monday (which IS reliable)
 * sidesteps that entirely and keeps this frontend helper the single
 * source of truth for date display, matching `weeksToHierarchy` in
 * utilization-search-page.tsx and employee-utilization-page.tsx
 * (Month "Apr 2026", Week "13 Apr 2026").
 *
 * Grouping keys stay synthetic (`__year::<yyyy>`, `__month::<yyyy>-<mm>`)
 * so months in different years with the same short-month label still
 * nest correctly. */
export function weekHierarchyToItems(
  hierarchy: WeekHierarchyEntry[] | undefined,
): HierarchicalItem[] {
  const items: HierarchicalItem[] = []
  const seenYears = new Set<string>()
  const seenMonths = new Set<string>()
  for (const e of hierarchy ?? []) {
    const d = new Date(`${e.week}T00:00:00`)
    if (Number.isNaN(d.getTime())) continue
    const year = String(d.getFullYear())
    // MM (1-12) padded — grouping key only, not shown to the user.
    const monthNum = String(d.getMonth() + 1).padStart(2, '0')
    const yearKey = `__year::${year}`
    const monthKey = `__month::${year}-${monthNum}`
    if (!seenYears.has(yearKey)) {
      seenYears.add(yearKey)
      items.push({ value: yearKey, label: year, isGroup: true })
    }
    if (!seenMonths.has(monthKey)) {
      seenMonths.add(monthKey)
      items.push({
        value: monthKey,
        label: WEEK_MONTH_FMT.format(d),
        isGroup: true,
        parent: yearKey,
      })
    }
    items.push({ value: e.week, label: WEEK_DAY_FMT.format(d), parent: monthKey })
  }
  return items
}

export interface FilterOptions {
  weeks: string[]
  /** Year > Month > Week nesting for the cascading date filter. */
  week_hierarchy: WeekHierarchyEntry[]
  regions: string[]
  markets: string[]
  /** Region > Market hierarchy for the Utilization Home unified
   * Region/Market filter (union of roster and booking taxonomies). */
  region_market_hierarchy: RegionMarketOption[]
  departments: string[]
  entities: string[]
  holdings: string[]
  hours_types: string[]
}

export interface HoldingProjects {
  holding: string
  projects: string[]
}
export interface HoldingsProjectsResponse {
  items: HoldingProjects[]
}

export interface UtilizationRecord {
  week_start: string
  date: string
  employee: string
  project: string
  holding: string
  hours_type: string
  hours: number
  region?: string
  department?: string
  team?: string
}
export interface RecordsSummary {
  total_hours: number
  client_hours: number
  internal_hours: number
  total_projects: number
  average_hours: number
}
export interface RecordsResponse {
  items: UtilizationRecord[]
  total: number
  summary: RecordsSummary
}
// Each filter field accepts either a single value or an array of values.
// Arrays are serialized as repeated query params (`?region=EMEA&region=AMER`)
// by the `paramsSerializer` on `useUtilizationRecords` below — matching what
// `GET /api/v1/utilization/records` expects (OR within a field, AND across
// fields). Do NOT let axios's default serializer handle these: its default
// for arrays produces `?region[]=EMEA&region[]=AMER` / comma-joined values
// depending on config, neither of which FastAPI's `Query(None)` list parsing
// accepts.
export interface RecordsFilters {
  week?: string | string[]
  region?: string | string[]
  market?: string | string[]
  department?: string | string[]
  entity?: string | string[]
  holding?: string | string[]
  hours_type?: string | string[]
  limit?: number
  offset?: number
}

export interface EmployeeHoursByProject {
  project: string
  total_hours: number
}
export interface EmployeeHoursByWeek {
  week_start: string
  client_hours: number
  internal_hours: number
}
export interface EmployeeUtilization {
  employee: string
  total_hours: number
  client_hours: number
  internal_hours: number
  total_projects: number
  hours_by_project: EmployeeHoursByProject[]
  hours_by_week: EmployeeHoursByWeek[]
}

export interface ProjectHoursByEmployee {
  employee: string
  client_hours: number
  internal_hours: number
}
export interface ProjectHoursByWeek {
  week_start: string
  client_hours: number
  internal_hours: number
}
export interface ProjectDetailRow {
  employee: string
  project: string
  region: string
  department: string
}
export interface ProjectUtilization {
  holding: string
  total_hours: number
  client_hours: number
  internal_hours: number
  hours_by_employee: ProjectHoursByEmployee[]
  hours_by_week: ProjectHoursByWeek[]
  detail: ProjectDetailRow[]
}

export interface WeeklyUtilizationPoint {
  week_start: string
  avg_weekly_utilization_pct: number
}
export interface UtilizationSplit {
  high: number
  moderate: number
  low: number
}
export interface EmployeeRankingRow {
  employee: string
  period_utilization_pct: number
}
export interface UtilizationOverview {
  average_period_utilization_pct: number
  total_employees: number
  latest_week_utilization_pct: number
  weekly_trend: WeeklyUtilizationPoint[]
  utilization_split: UtilizationSplit
  employee_ranking: EmployeeRankingRow[]
}

// Filters accepted by the four booking-aggregation endpoints below —
// same shape as `RecordsFilters` minus `limit`/`offset`. All four
// endpoints share one FastAPI dependency (`_booking_filter_params` in
// `backend/app/api/utilization.py`) so they cannot diverge; the array
// query params are serialized as repeated keys (`?region=EMEA&region=AMER`)
// via `paramsSerializer: { indexes: null }`, matching FastAPI's list
// parsing.
export type BookingChartFilters = Omit<RecordsFilters, 'limit' | 'offset'>

export function useUtilizationSummary(filters: BookingChartFilters = {}) {
  return useQuery({
    queryKey: ['utilization', 'summary', filters],
    queryFn: async () =>
      (
        await apiClient.get<UtilizationSummary>('/v1/utilization/summary', {
          params: filters,
          paramsSerializer: { indexes: null },
        })
      ).data,
    placeholderData: (prev) => prev,
  })
}

export function useUtilizationWeeklyTrend(filters: BookingChartFilters = {}) {
  return useQuery({
    queryKey: ['utilization', 'weekly-trend', filters],
    queryFn: async () =>
      (
        await apiClient.get<WeeklyTrendResponse>('/v1/utilization/weekly-trend', {
          params: filters,
          paramsSerializer: { indexes: null },
        })
      ).data,
    placeholderData: (prev) => prev,
  })
}

export function useUtilizationByRegion(filters: BookingChartFilters = {}) {
  return useQuery({
    queryKey: ['utilization', 'by-region', filters],
    queryFn: async () =>
      (
        await apiClient.get<ByRegionResponse>('/v1/utilization/by-region', {
          params: filters,
          paramsSerializer: { indexes: null },
        })
      ).data,
    placeholderData: (prev) => prev,
  })
}

export function useUtilizationByRegionMarket(filters: BookingChartFilters = {}) {
  return useQuery({
    queryKey: ['utilization', 'by-region-market', filters],
    queryFn: async () =>
      (
        await apiClient.get<ByRegionMarketResponse>('/v1/utilization/by-region-market', {
          params: filters,
          paramsSerializer: { indexes: null },
        })
      ).data,
    placeholderData: (prev) => prev,
  })
}

export function useUtilizationHoldingsProjects() {
  return useQuery({
    queryKey: ['utilization', 'holdings-projects'],
    queryFn: async () =>
      (await apiClient.get<HoldingsProjectsResponse>('/v1/utilization/holdings-projects')).data,
  })
}

export function useUtilizationFilterOptions() {
  return useQuery({
    queryKey: ['utilization', 'filter-options'],
    queryFn: async () =>
      (await apiClient.get<FilterOptions>('/v1/utilization/filter-options')).data,
  })
}

export function useUtilizationRecords(filters: RecordsFilters) {
  return useQuery({
    queryKey: ['utilization', 'records', filters],
    queryFn: async () =>
      (
        await apiClient.get<RecordsResponse>('/v1/utilization/records', {
          params: filters,
          // `indexes: null` makes axios serialize array params as repeated
          // keys (`?region=EMEA&region=AMER`) instead of its default
          // `region[]=EMEA&region[]=AMER`, which is the format
          // `GET /api/v1/utilization/records` expects via FastAPI's
          // `Query(None)` list parsing.
          paramsSerializer: { indexes: null },
        })
      ).data,
    placeholderData: (prev) => prev,
  })
}

const PAGE_LIMIT = 500

/**
 * Fetches ALL records matching `filters` by paginating through
 * `/utilization/records` (max 500/page) and concatenating items. Used to
 * derive client-side aggregations (distinct employee counts, weekly
 * breakdowns) that the summary/weekly-trend/by-region endpoints don't
 * support filtering on yet. `summary` on the response is the backend's
 * already-filtered aggregate (accurate regardless of pagination).
 */
export function useUtilizationRecordsAll(filters: Omit<RecordsFilters, 'limit' | 'offset'>) {
  return useQuery({
    queryKey: ['utilization', 'records-all', filters],
    queryFn: async () => {
      // `indexes: null` serializes array params (region/market/week) as
      // repeated keys (`?region=EMEA&region=AMER`) — the form FastAPI's
      // `Query(None)` list parsing reads. Without it axios sends `region[]=`,
      // which the backend ignores, silently dropping every multi-value
      // filter (the single-page `useUtilizationRecords` already sets this).
      const first = await apiClient.get<RecordsResponse>('/v1/utilization/records', {
        params: { ...filters, limit: PAGE_LIMIT, offset: 0 },
        paramsSerializer: { indexes: null },
      })
      const items = [...first.data.items]
      const total = first.data.total
      let offset = PAGE_LIMIT
      while (offset < total) {
        const page = await apiClient.get<RecordsResponse>('/v1/utilization/records', {
          params: { ...filters, limit: PAGE_LIMIT, offset },
          paramsSerializer: { indexes: null },
        })
        items.push(...page.data.items)
        offset += PAGE_LIMIT
      }
      return { items, total, summary: first.data.summary }
    },
    placeholderData: (prev) => prev,
  })
}

export function useEmployeeUtilization(employee: string | undefined) {
  return useQuery({
    queryKey: ['utilization', 'employee', employee],
    queryFn: async () => {
      try {
        return (
          await apiClient.get<EmployeeUtilization>(
            `/v1/utilization/employees/${encodeURIComponent(employee ?? '')}`,
          )
        ).data
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status
        if (status === 404) return null
        throw err
      }
    },
    enabled: !!employee,
  })
}

export function useProjectUtilization(holding: string | undefined) {
  return useQuery({
    queryKey: ['utilization', 'project', holding],
    queryFn: async () => {
      try {
        return (
          await apiClient.get<ProjectUtilization>(
            `/v1/utilization/projects/${encodeURIComponent(holding ?? '')}`,
          )
        ).data
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status
        if (status === 404) return null
        throw err
      }
    },
    enabled: !!holding,
  })
}

export function useUtilizationOverview() {
  return useQuery({
    queryKey: ['utilization', 'overview'],
    queryFn: async () =>
      (await apiClient.get<UtilizationOverview>('/v1/utilization/overview')).data,
  })
}
