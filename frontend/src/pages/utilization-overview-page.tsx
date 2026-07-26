import * as React from 'react'
import { Percent, Users, Gauge } from 'lucide-react'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { CustomLineChart } from '@/components/dashboard/custom-line-chart'
import { CustomDonutChart } from '@/components/dashboard/custom-donut-chart'
import { CustomBarChart } from '@/components/dashboard/custom-bar-chart'
import { FilterSelect } from '@/components/dashboard/filter-select'
import { FilterControl } from '@/components/dashboard/filter-control'
import { HierarchicalMultiSelect } from '@/components/dashboard/hierarchical-multi-select'
import {
  regionMarketHierarchyToItems,
  splitRegionMarketSelection,
  weekHierarchyToItems,
  useUtilizationFilterOptions,
  useUtilizationOverview,
} from '@/lib/utilization-api'
import { filterLabel, useFilterConfig } from '@/lib/filter-config'
import { UTILIZATION_SPLIT_COLORS } from '@/lib/chart-colors'
import { withTruncatedLabels } from '@/lib/chart-labels'

export function UtilizationOverviewPage() {
  // Same filter-row pattern as UtilizationHomePage: read filter DEFINITIONS
  // from `useFilterConfig('booking')` (page label + type live in YAML, not
  // hardcoded here), then use `useUtilizationFilterOptions` for the option
  // values. `applies_to_pages` on each filter now includes
  // `utilization-overview` (2026-07-26) so the same filters appear here.
  const filterOptions = useUtilizationFilterOptions()
  const filterConfig = useFilterConfig('booking')

  const [hoursType, setHoursType] = React.useState<string | undefined>()
  const [regionMarket, setRegionMarket] = React.useState<string[]>([])
  const [weeks, setWeeks] = React.useState<string[]>([])
  const [department, setDepartment] = React.useState<string | undefined>()

  const regionMarketItems = React.useMemo(
    () => regionMarketHierarchyToItems(filterOptions.data?.region_market_hierarchy),
    [filterOptions.data],
  )
  const dateItems = React.useMemo(
    () => weekHierarchyToItems(filterOptions.data?.week_hierarchy),
    [filterOptions.data],
  )

  const filters = React.useMemo(
    () => ({
      hours_type: hoursType,
      ...splitRegionMarketSelection(regionMarket),
      week: weeks,
      department,
    }),
    [hoursType, regionMarket, weeks, department],
  )

  const overview = useUtilizationOverview(filters)

  // Memoized, keyed on overview.data rather than the whole query object:
  // react-query re-renders this component on background-refetch state
  // changes (isFetching/dataUpdatedAt) even when `data` itself hasn't
  // changed, which would otherwise recreate these arrays and force the
  // now-React.memo'd charts to redraw for no reason.
  const trendData = React.useMemo(
    () =>
      overview.data?.weekly_trend.map((w) => ({
        week: w.week_start,
        'Avg Weekly Utilization %': +(w.avg_weekly_utilization_pct * 100).toFixed(1),
      })) ?? [],
    [overview.data],
  )

  const splitData = React.useMemo(
    () =>
      overview.data
        ? [
            { name: 'High', value: overview.data.utilization_split.high },
            { name: 'Moderate', value: overview.data.utilization_split.moderate },
            { name: 'Low', value: overview.data.utilization_split.low },
          ]
        : [],
    [overview.data],
  )
  const splitColors = React.useMemo(
    () => splitData.map((d) => UTILIZATION_SPLIT_COLORS[d.name] ?? 'gray'),
    [splitData],
  )

  const rankingData = React.useMemo(
    () =>
      withTruncatedLabels(
        overview.data?.employee_ranking.map((r) => ({
          name: r.employee,
          value: +(r.period_utilization_pct * 100).toFixed(1),
        })) ?? [],
        'name',
      ),
    [overview.data],
  )

  const hasActiveFilters =
    !!hoursType || regionMarket.length > 0 || weeks.length > 0 || !!department
  const emptyMsg = hasActiveFilters
    ? 'No booking hours match the selected filters. Try clearing a filter.'
    : undefined

  return (
    <div className="space-y-5">
      <div className="grid w-full grid-cols-1 gap-3 sm:flex sm:w-auto sm:flex-wrap">
        <FilterSelect
          label={filterLabel(filterConfig.data?.filters, 'hours_type', 'Hours Type')}
          value={hoursType}
          options={filterOptions.data?.hours_types ?? []}
          onChange={setHoursType}
        />
        <FilterControl
          label={`${filterLabel(filterConfig.data?.filters, 'region', 'Region')}/${filterLabel(filterConfig.data?.filters, 'market', 'Market')}`}
        >
          <HierarchicalMultiSelect
            items={regionMarketItems}
            selected={regionMarket}
            onChange={setRegionMarket}
            placeholder="All"
          />
        </FilterControl>
        <FilterControl label={filterLabel(filterConfig.data?.filters, 'week', 'Month / Week')}>
          <HierarchicalMultiSelect
            items={dateItems}
            selected={weeks}
            onChange={setWeeks}
            placeholder="All Weeks"
          />
        </FilterControl>
        <FilterSelect
          label={filterLabel(filterConfig.data?.filters, 'department', 'Department')}
          value={department}
          options={filterOptions.data?.departments ?? []}
          onChange={setDepartment}
        />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <KpiCard
          label="Average Period Utilization"
          value={overview.data ? `${(overview.data.average_period_utilization_pct * 100).toFixed(1)}%` : '—'}
          loading={overview.isLoading}
          icon={Percent}
          iconTone="blue"
        />
        <KpiCard
          label="Total Employees"
          value={overview.data?.total_employees ?? '—'}
          loading={overview.isLoading}
          icon={Users}
          iconTone="blue"
        />
        <KpiCard
          label="Latest Week Utilization"
          value={overview.data ? `${(overview.data.latest_week_utilization_pct * 100).toFixed(1)}%` : '—'}
          loading={overview.isLoading}
          icon={Gauge}
          iconTone="blue"
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <ChartCard
          title="Weekly Utilization Trend"
          isLoading={overview.isLoading}
          isError={overview.isError}
          isEmpty={trendData.length === 0}
          emptyMessage={emptyMsg}
        >
          <CustomLineChart
            data={trendData}
            index="week"
            category="Avg Weekly Utilization %"
            yAxisLabel="Utilization %"
            xAxisLabel="Week"
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Utilization Split"
          subtitle="High / Moderate / Low bands"
          isLoading={overview.isLoading}
          isError={overview.isError}
          isEmpty={splitData.every((d) => d.value === 0)}
          provisional
          provisionalNote="Utilization bands (High >= 90%, Moderate 80-90%, Low < 80%) are PROVISIONAL — thresholds not yet confirmed against a real Power BI DAX band measure. Underlying values are booking-derived Formula A as of 2026-07-26 (ground-truth file no longer consulted at runtime); QA reconciliation between Formula A and the ground truth is available via /api/v1/qa/reconcile. See METRICS.md Page 8."
        >
          <CustomDonutChart data={splitData} colors={splitColors} className="h-full" />
        </ChartCard>
      </div>

      <ChartCard
        title="Employee Period Utilization %"
        subtitle="Ranked, all employees"
        isLoading={overview.isLoading}
        isError={overview.isError}
        isEmpty={rankingData.length === 0}
        emptyMessage={emptyMsg}
        height="h-80"
      >
        {/* Many employees at the page's normal chart height would squash
            every bar into an unreadable sliver, silently hiding most of
            the data even though it's all present in the DOM (the same
            failure mode flagged on Workforce's seniority chart). `rowHeightPx`
            gives each bar a fixed height and lets CustomBarChart scroll its
            plot internally instead. */}
        <CustomBarChart
          data={rankingData}
          index="name"
          category="value"
          tooltipValueLabel="Utilization %"
          layout="vertical"
          yAxisWidth={140}
          yAxisLabel="Employee"
          xAxisLabel="Utilization %"
          showLegend={false}
          rowHeightPx={32}
          className="h-full"
        />
      </ChartCard>
    </div>
  )
}
