import * as React from 'react'

import {
  useRosterAttritionDetail,
  useRosterEmployeesAll,
  useRosterSummary,
  useRosterBreakdowns,
  useRosterTrends,
} from '@/lib/roster-api'
import {
  ALL,
  buildOptions,
  buildRegionMarketItems,
  buildServerFilters,
  distinctValues,
  regionMarketServerFilters,
  type FilterValues,
} from '@/lib/employee-filters'
import type { HierarchicalFilterDef } from '@/components/dashboard/filter-bar'

/**
 * Shared data-fetching + filter state for the HR Analytics page
 * (`/hr-analytics`). Every section on the page filters by the same
 * Month Year / Status / Department / Region controls, so the queries and
 * filter state live here to avoid duplicating fetch/filter-option logic.
 */
export function useHrAnalyticsFilters() {


  // Unfiltered list, used ONLY to populate the filter dropdowns — if this
  // followed the filters, choosing one would erase the other options.
  const allEmployeesQuery = useRosterEmployeesAll()
  const employees = allEmployeesQuery.data?.items ?? []

  const [filters, setFilters] = React.useState<FilterValues>({
    monthYear: ALL,
    status: ALL,
    department: ALL,
  })
  const setFilter = (key: string, value: string) =>
    setFilters((prev) => ({ ...prev, [key]: value }))
  // Region/Market is one nested multi-select (like the Search page).
  const [regionMarket, setRegionMarket] = React.useState<string[]>([])
  const regionMarketItems = React.useMemo(
    () => buildRegionMarketItems(employees),
    [employees],
  )

  // KPIs come from the server WITH the filters applied, so they use the
  // YAML metric definitions rather than being recomputed here against
  // hardcoded status strings. ALL means "no filter" and is dropped.
  // `monthYear` is excluded — it filters the pre-aggregated trend/attrition
  // arrays in the browser (see `monthFilter`), not the roster on the server.
  const serverFilters = React.useMemo(
    () => ({ ...buildServerFilters(filters), ...regionMarketServerFilters(regionMarket) }),
    [filters, regionMarket],
  )
  const summary = useRosterSummary(serverFilters)
  const breakdowns = useRosterBreakdowns(serverFilters)
  const trends = useRosterTrends(serverFilters)
  const attrition = useRosterAttritionDetail(serverFilters)
  // The rows the page actually displays, filtered server-side like the KPIs.
  const employeesQuery = useRosterEmployeesAll(serverFilters)

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
  ]
  const hierarchicalFilters: HierarchicalFilterDef[] = [
    {
      key: 'regionMarket',
      label: 'Region/Market',
      items: regionMarketItems,
      selected: regionMarket,
      onChange: setRegionMarket,
    },
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

  return {
    summary,
    breakdowns,
    trends,
    attrition,
    employeesQuery,
    filters,
    setFilter,
    filterDefs,
    hierarchicalFilters,
    monthFilter,
  }
}
