import * as React from 'react'

import {
  useRosterAttritionDetail,
  useRosterEmployeesAll,
  useRosterSummary,
  useRosterTrends,
} from '@/lib/roster-api'
import { ALL, buildOptions, distinctValues, type FilterValues } from '@/lib/employee-filters'

/**
 * Shared data-fetching + filter state for the HR Analytics page
 * (`/hr-analytics`). Every section on the page filters by the same
 * Month Year / Status / Department / Region controls, so the queries and
 * filter state live here to avoid duplicating fetch/filter-option logic.
 */
export function useHrAnalyticsFilters() {
  const summary = useRosterSummary()
  const trends = useRosterTrends()
  const attrition = useRosterAttritionDetail()
  const employeesQuery = useRosterEmployeesAll()
  const employees = employeesQuery.data?.items ?? []

  const [filters, setFilters] = React.useState<FilterValues>({
    monthYear: ALL,
    status: ALL,
    department: ALL,
    region: ALL,
  })
  const setFilter = (key: string, value: string) =>
    setFilters((prev) => ({ ...prev, [key]: value }))

  const monthOptions = buildOptions(
    (trends.data?.month_wise_closing_headcount ?? []).map((m) => m.month),
  )
  const filterDefs = [
    { key: 'monthYear', label: 'Month Year', options: monthOptions },
    { key: 'status', label: 'Status', options: buildOptions(distinctValues(employees, 'status')) },
    {
      key: 'department',
      label: 'Department',
      options: buildOptions(distinctValues(employees, 'designation')),
    },
    { key: 'region', label: 'Region/Market', options: buildOptions(distinctValues(employees, 'region')) },
  ]

  // Month Year filters trend/resignation charts directly by month label
  // (these come from the /roster/trends and /roster/attrition-detail
  // endpoints, which are pre-aggregated by month — filtering the returned
  // arrays is exact, not an approximation). Memoized on `filters.monthYear`
  // so callers building their own `useMemo`'d chart data (see
  // hr-analytics-page.tsx) can depend on `monthFilter` itself instead of a
  // fresh closure identity every render.
  const monthFilter = React.useCallback(
    (month: string) => filters.monthYear === ALL || filters.monthYear === month,
    [filters.monthYear],
  )

  return { summary, trends, attrition, employeesQuery, filters, setFilter, filterDefs, monthFilter }
}
