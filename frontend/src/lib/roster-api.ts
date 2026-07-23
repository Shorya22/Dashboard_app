import { useQuery } from '@tanstack/react-query'
import { apiClient } from './api-client'

// Types mirror backend/app schemas (see /api/v1/openapi.json). Keep field
// names exact — measure names are confirmed against the data-model skill,
// don't rename them to generic BI terms.

export interface RosterSummary {
  active_employees: number
  inactive_employees: number
  total_employees: number
  active_pct: number
  attrition_pct: number
  voluntary_leavers: number
  involuntary_leavers: number
  gcc_employees: number
  non_gcc_employees: number
  average_experience_yrs: number
  average_hexaware_experience: number
  pending_mapping_count: number
  closing_headcount: number
  opening_headcount: number
  joiners: number
  exits: number
  clients_covered: number
  projects: number
  senior_lead_employees: number
  departments: number
  skills_covered: number
}

export interface RosterBreakdowns {
  strategic_pool: number
  workforce_category_split: Record<string, number>
  status_split: Record<string, number>
  workforce_by_type: Record<string, number>
  headcount_by_region: Record<string, number>
  workforce_by_working_entity: Record<string, number>
  headcount_by_seniority: Record<string, number>
  workforce_by_experience_band: Record<string, number>
  workforce_by_seniority_category: Record<string, number>
}

export interface MonthClosingHeadcount {
  month: string
  closing_headcount: number
}
export interface MonthJoinersVsLeavers {
  month: string
  joiners: number
  exits: number
}
export interface RosterTrends {
  month_wise_closing_headcount: MonthClosingHeadcount[]
  monthly_joiners_vs_leavers: MonthJoinersVsLeavers[]
}

export interface MonthResignation {
  month: string
  exits: number
}
export interface ExitRecord {
  name: string | null
  designation: string | null
  primary_skill: string | null
  region: string | null
  market: string | null
  type: string | null
  lwd: string | null
  reason_for_leaving: string | null
  status: string | null
}
export interface RosterAttritionDetail {
  month_wise_resignation: MonthResignation[]
  voluntary_involuntary_split: Record<string, number>
  exits_table: ExitRecord[]
}

export interface SkillByExperienceBand {
  primary_skill: string
  experience_band: string
  count: number
}
export interface SkillBySeniorityCategory {
  primary_skill: string
  seniority_category: string
  count: number
}
export interface SkillByRegion {
  primary_skill: string
  region: string
  count: number
}
export interface WorkforceDetailByRegion {
  region: string
  seniority_category: string
  count: number
}
export interface RosterSkills {
  skill_bifurcation_by_experience_band: SkillByExperienceBand[]
  skill_bifurcation_by_seniority_category: SkillBySeniorityCategory[]
  skill_bifurcation_by_region: SkillByRegion[]
  workforce_details_by_region: WorkforceDetailByRegion[]
}

export interface EmployeeRecord {
  employee_id: string | number | null
  name: string | null
  grade: string | null
  designation: string | null
  work_location: string | null
  total_experience: number | null
  working_entity: string | null
  client: string | null
  seniority_level: string | null
  region: string | null
  market: string | null
  status: string | null
  type: string | null
  primary_skill: string | null
  skill: string | null
  supervisor: string | null
}
export interface DirectoryColumn {
  key: string
  label: string
  display?: 'serial' | 'experience' | 'grade' | null
}
export interface EmployeeDirectoryResponse {
  items: EmployeeRecord[]
  total: number
  columns?: DirectoryColumn[]
}

export interface BookingSummary {
  total_hours: number
  client_hours: number
  internal_hours: number
  client_hours_pct: number
  internal_hours_pct: number
  /** Hours grouped by `Booked Hours Type`, from the chart declared in
   *  booking_metrics.yaml. Backs the Internal-v-Client donut. */
  hours_split: Record<string, number>
  total_clients: number
  total_projects: number
  total_regions: number
  markets_covered: number
}

// Page filters are applied SERVER-side: the roster endpoints accept
// status/department/region and compute every number from the YAML metric
// definitions. Pages pass their filter state straight through rather than
// re-deriving KPIs in the browser against hardcoded status strings, which
// duplicated each definition and drifted the moment config changed.
// Keys must match the `filters:` block in backend
// configs/roster_metrics.yaml. `filterQuery` passes every set key through,
// so the backend (which reads exactly its declared filters) is the single
// source of truth for which of these actually filter.
export type RosterFilterParams = {
  status?: string
  department?: string
  region?: string
  skill?: string
  type?: string
  allocation?: string
  grade?: string
  experience?: string
  seniorityCategory?: string
}

function filterQuery(filters?: RosterFilterParams) {
  const params: Record<string, string> = {}
  for (const [key, value] of Object.entries(filters ?? {})) {
    if (value) params[key] = value
  }
  return params
}

export function useRosterSummary(filters?: RosterFilterParams) {
  const params = filterQuery(filters)
  return useQuery({
    queryKey: ['roster', 'summary', params],
    queryFn: async () =>
      (await apiClient.get<RosterSummary>('/v1/roster/summary', { params })).data,
  })
}

export function useRosterBreakdowns(filters?: RosterFilterParams) {
  const params = filterQuery(filters)
  return useQuery({
    queryKey: ['roster', 'breakdowns', params],
    queryFn: async () =>
      (await apiClient.get<RosterBreakdowns>('/v1/roster/breakdowns', { params })).data,
  })
}

export function useRosterTrends(filters?: RosterFilterParams) {
  const params = filterQuery(filters)
  return useQuery({
    queryKey: ['roster', 'trends', params],
    queryFn: async () =>
      (await apiClient.get<RosterTrends>('/v1/roster/trends', { params })).data,
  })
}

export function useRosterAttritionDetail(filters?: RosterFilterParams) {
  const params = filterQuery(filters)
  return useQuery({
    queryKey: ['roster', 'attrition-detail', params],
    queryFn: async () =>
      (await apiClient.get<RosterAttritionDetail>('/v1/roster/attrition-detail', { params })).data,
  })
}

export function useRosterSkills(filters?: RosterFilterParams) {
  const params = filterQuery(filters)
  return useQuery({
    queryKey: ['roster', 'skills', params],
    queryFn: async () =>
      (await apiClient.get<RosterSkills>('/v1/roster/skills', { params })).data,
  })
}

export function useRosterEmployees(limit: number, offset: number) {
  return useQuery({
    queryKey: ['roster', 'employees', limit, offset],
    queryFn: async () =>
      (
        await apiClient.get<EmployeeDirectoryResponse>('/v1/roster/employees', {
          params: { limit, offset },
        })
      ).data,
    placeholderData: (prev) => prev,
  })
}

// Fetches the full roster in one page for pages that need to filter/recompute
// client-side (see lib/employee-filters.ts) — the roster is only 52 rows, so
// one request comfortably covers it instead of paginating.
export function useRosterEmployeesAll(filters?: RosterFilterParams) {
  const params = { limit: 500, offset: 0, ...filterQuery(filters) }
  return useQuery({
    queryKey: ['roster', 'employees', 'all', params],
    queryFn: async () =>
      (await apiClient.get<EmployeeDirectoryResponse>('/v1/roster/employees', { params }))
        .data,
  })
}

export function useBookingSummary() {
  return useQuery({
    queryKey: ['booking', 'summary'],
    queryFn: async () => (await apiClient.get<BookingSummary>('/v1/booking/summary')).data,
  })
}
