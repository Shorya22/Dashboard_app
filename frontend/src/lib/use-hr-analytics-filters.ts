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
import { filterLabel, useFilterConfig } from '@/lib/filter-config'
import { monthsToHierarchy } from '@/lib/utilization-api'
import type { HierarchicalFilterDef } from '@/components/dashboard/filter-bar'

/**
 * Shared data-fetching + filter state for the HR Analytics page
 * (`/hr-analytics`). Every KPI card AND every trend/attrition chart on
 * the page reads from queries filtered by the same Month / Year /
 * Status / Department / Region controls. Month / Year is a real
 * server-side filter (`time_filter: true` in `roster_metrics.yaml`) so
 * both the roster rows the KPIs count over AND the pre-aggregated
 * monthly arrays get narrowed in one round trip — no client-side
 * membership check needed anymore.
 */
export function useHrAnalyticsFilters() {
  const filterConfig = useFilterConfig('roster')
  const labelOf = (key: string, fallback: string) =>
    filterLabel(filterConfig.data?.filters, key, fallback)


  // Unfiltered list, used ONLY to populate the filter dropdowns — if this
  // followed the filters, choosing one would erase the other options.
  const allEmployeesQuery = useRosterEmployeesAll()
  const employees = allEmployeesQuery.data?.items ?? []

  const [filters, setFilters] = React.useState<FilterValues>({
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
  // Month/Year is a Year > Month hierarchical multi-select. Selected
  // leaves are "Mon YYYY" strings sent to the backend as `month_year`
  // repeated query params (same shape as region/market).
  const [monthYear, setMonthYear] = React.useState<string[]>([])

  // Full filter state, sent as-is to every roster endpoint. `month_year`
  // is included: the backend narrows both the roster rows the KPIs count
  // over and the trend/attrition monthly arrays, so every widget on the
  // page reacts to the picker in a single round trip.
  const serverFilters = React.useMemo(
    () => ({
      ...buildServerFilters(filters),
      ...regionMarketServerFilters(regionMarket),
      month_year: monthYear.length ? monthYear : undefined,
    }),
    [filters, regionMarket, monthYear],
  )
  const summary = useRosterSummary(serverFilters)
  const breakdowns = useRosterBreakdowns(serverFilters)
  const trends = useRosterTrends(serverFilters)
  const attrition = useRosterAttritionDetail(serverFilters)
  // The rows the page actually displays, filtered server-side like the KPIs.
  const employeesQuery = useRosterEmployeesAll(serverFilters)

  // Options for the Month / Year dropdown come from an UNFILTERED trends
  // call — if we read them from `trends.data` (the filtered response)
  // then picking "Apr 2026" would immediately narrow the option list to
  // just April, hiding every other month the user might want to pick.
  const allTrends = useRosterTrends()
  const monthItems = React.useMemo(
    () =>
      monthsToHierarchy(
        (allTrends.data?.month_wise_closing_headcount ?? []).map((m) => m.month),
      ),
    [allTrends.data],
  )
  const filterDefs = [
    { key: 'status', label: labelOf('status', 'Status'), options: buildOptions(distinctValues(employees, 'status')) },
    {
      key: 'department',
      label: labelOf('department', 'Department'),
      options: buildOptions(distinctValues(employees, 'designation')),
    },
  ]
  const hierarchicalFilters: HierarchicalFilterDef[] = [
    {
      key: 'monthYear',
      label: labelOf('month_year', 'Month / Year'),
      items: monthItems,
      selected: monthYear,
      onChange: setMonthYear,
    },
    {
      key: 'regionMarket',
      label: `${labelOf('region', 'Region')}/${labelOf('market', 'Market')}`,
      items: regionMarketItems,
      selected: regionMarket,
      onChange: setRegionMarket,
    },
  ]

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
  }
}
