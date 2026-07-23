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

/** Build the Region > Market tree for the hierarchical Region/Market
 * multi-select, matching the Search page: Region parents from the flat
 * `regions` list, Market children from the (region, market) pairs of
 * `/utilization/by-region-market` (the only endpoint that associates the
 * two). Market values keep the raw string the API filters on, but display
 * the confirmed alias (BN -> BENO, Technology -> AMER). */
export function buildRegionMarketItems(
  regions: string[] | undefined,
  pairs: { region: string; market: string }[] | undefined,
): HierarchicalItem[] {
  const items: HierarchicalItem[] = (regions ?? []).map((r) => ({ value: r, label: r }))
  const seen = new Set<string>()
  for (const { region, market } of pairs ?? []) {
    const key = `${region}::${market}`
    if (seen.has(key)) continue
    seen.add(key)
    items.push({ value: key, label: marketDisplayLabel(market), parent: region })
  }
  return items
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

/** Build the Month > Week tree for the hierarchical date multi-select, from
 * the backend's Year>Month>Week hierarchy. Each Month (the booking sheet's
 * own label, e.g. "May 26") is a synthetic parent group; each Week is a
 * selectable leaf whose value is the ISO week-start date — so ticking a month
 * selects all its weeks, and the filter always sends exact `week` values.
 * Entries arrive week-sorted, so months render chronologically. */
export function weekHierarchyToItems(
  hierarchy: WeekHierarchyEntry[] | undefined,
): HierarchicalItem[] {
  return (hierarchy ?? []).map((e) => {
    const d = new Date(`${e.week}T00:00:00`)
    const dayLabel = d.toLocaleDateString(undefined, {
      day: '2-digit',
      month: 'short',
    })
    return { value: e.week, label: dayLabel, parent: e.month }
  })
}

export interface FilterOptions {
  weeks: string[]
  /** Year > Month > Week nesting for the cascading date filter. */
  week_hierarchy: WeekHierarchyEntry[]
  regions: string[]
  markets: string[]
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

export function useUtilizationSummary() {
  return useQuery({
    queryKey: ['utilization', 'summary'],
    queryFn: async () => (await apiClient.get<UtilizationSummary>('/v1/utilization/summary')).data,
  })
}

export function useUtilizationWeeklyTrend() {
  return useQuery({
    queryKey: ['utilization', 'weekly-trend'],
    queryFn: async () =>
      (await apiClient.get<WeeklyTrendResponse>('/v1/utilization/weekly-trend')).data,
  })
}

export function useUtilizationByRegion() {
  return useQuery({
    queryKey: ['utilization', 'by-region'],
    queryFn: async () => (await apiClient.get<ByRegionResponse>('/v1/utilization/by-region')).data,
  })
}

export function useUtilizationByRegionMarket() {
  return useQuery({
    queryKey: ['utilization', 'by-region-market'],
    queryFn: async () =>
      (await apiClient.get<ByRegionMarketResponse>('/v1/utilization/by-region-market')).data,
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
