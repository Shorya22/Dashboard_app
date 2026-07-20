import * as React from 'react'
import { Users, Clock, Briefcase, Building2, FolderKanban } from 'lucide-react'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { FilterSelect } from '@/components/dashboard/filter-select'
import { CustomBarChart } from '@/components/dashboard/custom-bar-chart'
import {
  useUtilizationByRegionMarket,
  useUtilizationFilterOptions,
  useUtilizationRecordsAll,
  useUtilizationSummary,
} from '@/lib/utilization-api'
import { marketDisplayLabel, HOURS_TYPE_COLORS } from '@/lib/chart-colors'

// Hoisted to module scope so its array reference is stable across renders,
// matching CustomBarChart's React.memo (values are constant column/color
// pairs, not derived from any state).
const WEEKLY_HOURS_SERIES = [
  { category: 'Client Hours', color: HOURS_TYPE_COLORS['Client Hours'] },
  { category: 'Internal Hours', color: HOURS_TYPE_COLORS['Internal Hours'] },
]

export function UtilizationHomePage() {
  const filterOptions = useUtilizationFilterOptions()
  const byRegionMarket = useUtilizationByRegionMarket()
  const utilizationSummary = useUtilizationSummary()

  const [hoursType, setHoursType] = React.useState<string | undefined>()
  const [region, setRegion] = React.useState<string | undefined>()
  const [week, setWeek] = React.useState<string | undefined>()
  const [department, setDepartment] = React.useState<string | undefined>()

  const filters = React.useMemo(
    () => ({ hours_type: hoursType, region, week, department }),
    [hoursType, region, week, department],
  )

  const recordsAll = useUtilizationRecordsAll(filters)

  // Total Employees is the booking-sheet distinct employee count (the
  // real DAX measure is "Total Employeess" — typo preserved server-side —
  // exposed as `total_employees` on /utilization/summary). Read it from
  // that endpoint directly rather than re-deriving a distinct count from
  // paginated records, which doesn't apply the server's exact rules and
  // previously matched the ROSTER's Active count (47) instead of the
  // booking sheet's 46.
  const totalEmployees = utilizationSummary.data?.total_employees

  const weeklyData = React.useMemo(() => {
    if (!recordsAll.data) return []
    const byWeek = new Map<string, { 'Client Hours': number; 'Internal Hours': number }>()
    for (const r of recordsAll.data.items) {
      // Records with no week_start (a small number of malformed rows)
      // can't be bucketed into a real week — drop them rather than
      // grouping them under a stray "Unknown" bar, which also sorted
      // first and pushed a real week bucket out of view.
      if (!r.week_start) continue
      const entry = byWeek.get(r.week_start) ?? { 'Client Hours': 0, 'Internal Hours': 0 }
      if (r.hours_type === 'Client Hours') entry['Client Hours'] += r.hours
      else if (r.hours_type === 'Internal Hours') entry['Internal Hours'] += r.hours
      byWeek.set(r.week_start, entry)
    }
    return Array.from(byWeek.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([week_start, v]) => ({ week: week_start, ...v }))
  }, [recordsAll.data])

  // NOTE: `region`/`market` are not present on individual booking records
  // returned by /api/v1/utilization/records, and /utilization/by-region-market
  // doesn't accept filter query params — so this chart can't yet be
  // filtered client-side. Flagged to the team; see final report.
  //
  // Combined "Region/Market" label built from the two fields returned by
  // /utilization/by-region-market. The raw `Market (EC)` value is remapped
  // through the confirmed display alias (BN -> BENO, Technology -> AMER;
  // see `chart-colors.ts::MARKET_DISPLAY_ALIASES`) so the bar label matches
  // the Power BI reference; the raw value is never sent anywhere from this
  // read-only chart, so there's no submission concern here.
  const regionMarketData = React.useMemo(
    () =>
      byRegionMarket.data?.items.map((r) => ({
        name: `${r.region}/${marketDisplayLabel(r.market)}`,
        value: r.total_hours,
      })) ?? [],
    [byRegionMarket.data],
  )

  const isLoading = recordsAll.isLoading || utilizationSummary.isLoading
  const summary = recordsAll.data?.summary

  return (
    <div className="space-y-5">
      <div className="grid w-full grid-cols-1 gap-3 sm:flex sm:w-auto sm:flex-wrap">
        <FilterSelect
          label="Hours Type"
          value={hoursType}
          options={filterOptions.data?.hours_types ?? []}
          onChange={setHoursType}
        />
        <FilterSelect
          label="Region"
          value={region}
          options={filterOptions.data?.regions ?? []}
          onChange={setRegion}
        />
        <FilterSelect
          label="Week"
          value={week}
          options={filterOptions.data?.weeks ?? []}
          onChange={setWeek}
        />
        <FilterSelect
          label="Department"
          value={department}
          options={filterOptions.data?.departments ?? []}
          onChange={setDepartment}
        />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <KpiCard
          label="Total Employees"
          value={totalEmployees ?? '—'}
          loading={utilizationSummary.isLoading}
          icon={Users}
          iconTone="blue"
        />
        <KpiCard
          label="Total Hours"
          value={summary ? summary.total_hours.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
          loading={isLoading}
          icon={Clock}
          iconTone="blue"
        />
        <KpiCard
          label="Client Hours"
          value={summary ? summary.client_hours.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
          loading={isLoading}
          icon={Briefcase}
          iconTone="blue"
        />
        <KpiCard
          label="Internal Hours"
          value={summary ? summary.internal_hours.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
          loading={isLoading}
          icon={Building2}
          iconTone="blue"
        />
        <KpiCard
          label="Total Projects"
          value={summary?.total_projects ?? '—'}
          loading={isLoading}
          icon={FolderKanban}
          iconTone="blue"
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <ChartCard
          title="Weekly Hours Trend"
          subtitle="Client vs internal hours per week"
          isLoading={recordsAll.isLoading}
          isError={recordsAll.isError}
          isEmpty={weeklyData.length === 0}
        >
          <CustomBarChart
            data={weeklyData}
            index="week"
            series={WEEKLY_HOURS_SERIES}
            yAxisLabel="Hours"
            xAxisLabel="Week"
            showLegend
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Total Hours by Market(EC) and Region(EC)"
          subtitle="Combined Region/Market breakdown"
          isLoading={byRegionMarket.isLoading}
          isError={byRegionMarket.isError}
          isEmpty={regionMarketData.length === 0}
        >
          <CustomBarChart
            data={regionMarketData}
            index="name"
            category="value"
            color="amber"
            tooltipValueLabel="Hours"
            yAxisLabel="Hours"
            xAxisLabel="Region/Market"
            className="h-full"
          />
        </ChartCard>
      </div>
    </div>
  )
}
