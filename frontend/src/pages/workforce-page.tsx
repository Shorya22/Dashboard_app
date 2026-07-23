import * as React from 'react'
import { Users, UserCheck, UserX, Target, Building2, Briefcase } from 'lucide-react'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { FilterBar } from '@/components/dashboard/filter-bar'
import { CustomBarChart } from '@/components/dashboard/custom-bar-chart'
import { CustomDonutChart } from '@/components/dashboard/custom-donut-chart'
import { useRosterBreakdowns, useRosterEmployeesAll, useRosterSummary } from '@/lib/roster-api'
import { withTruncatedLabels } from '@/lib/chart-labels'
import { TYPE_COLORS, colorsForLabels } from '@/lib/chart-colors'
import {
  ALL,
  buildOptions,
  distinctValues,
  type FilterValues,
} from '@/lib/employee-filters'



export function WorkforcePage() {
  

  const employeesQuery = useRosterEmployeesAll()
  const employees = React.useMemo(() => employeesQuery.data?.items ?? [], [employeesQuery.data])

  const [filters, setFilters] = React.useState<FilterValues>({
    region: ALL,
    grade: ALL,
    department: ALL,
    skill: ALL,
  })
  const setFilter = (key: string, value: string) =>
    setFilters((prev) => ({ ...prev, [key]: value }))

  const filterDefs = [
    { key: 'region', label: 'Region/Market', options: buildOptions(distinctValues(employees, 'region')) },
    { key: 'grade', label: 'Grade', options: buildOptions(distinctValues(employees, 'grade')) },
    {
      key: 'department',
      label: 'Department',
      options: buildOptions(distinctValues(employees, 'designation')),
    },
    {
      // Reference PDF labels this single dropdown "Type/Primary Skill" —
      // filtering by Primary Skill since "Type" (GCC/Non-GCC) is already
      // covered by other pages and Primary Skill is the more distinctive
      // axis for this page's charts.
      key: 'skill',
      label: 'Type/Primary Skill',
      options: buildOptions(distinctValues(employees, 'primary_skill')),
    },
  ]

  // Memoized: this page's charts are now React.memo'd (custom-bar-chart.tsx
  // / custom-donut-chart.tsx), so keeping stable references here means an
  // unrelated re-render doesn't force every chart to redraw.
  const serverFilters = React.useMemo(
    () => ({
      status: filters.status === ALL ? undefined : filters.status,
      department: filters.department === ALL ? undefined : filters.department,
      region: filters.region === ALL ? undefined : filters.region,
    }),
    [filters.status, filters.department, filters.region],
  )
  const summary = useRosterSummary(serverFilters)
  const breakdowns = useRosterBreakdowns(serverFilters)

  const isLoading = employeesQuery.isLoading || summary.isLoading
  const isError = employeesQuery.isError

  // KPIs come from the server WITH this page's filters applied, so they use
  // the single YAML metric definitions instead of being recomputed here
  // against hardcoded status strings.
  const totalEmployees = summary.data?.total_employees
  const activeEmployees = summary.data?.active_employees
  const inactiveEmployees = summary.data?.inactive_employees
  const departmentsCount = summary.data?.departments
  const projectsCount = summary.data?.projects

  // Charts come from the server WITH this page's filters applied, same as
  // the KPIs. They were regrouped here from the filtered rows, which meant
  // re-implementing the definitions in the browser — including a JS copy of
  // the seniority normalisation and hardcoded "Seniority TBD" / "Type TBD"
  // labels that had to be kept in step with config by hand.
  const toChartData = (counts: Record<string, number> | undefined) =>
    Object.entries(counts ?? {}).map(([name, value]) => ({ name, value }))

  const seniorityData = React.useMemo(
    () =>
      withTruncatedLabels(toChartData(breakdowns.data?.headcount_by_seniority), 'name'),
    [breakdowns.data],
  )

  const typeData = React.useMemo(
    () => toChartData(breakdowns.data?.workforce_by_type),
    [breakdowns.data],
  )
  const typeColors = React.useMemo(
    () => colorsForLabels(typeData.map((d) => d.name), TYPE_COLORS),
    [typeData],
  )

  // Whatever regions the data actually contains — driven by the
  // headcount_by_region chart declared in roster_metrics.yaml (blanks
  // already labelled "Region TBD"). Replaces a hardcoded AMER/APAC/EMEA/
  // Hexaware list that showed an always-empty Hexaware bar and hid the
  // Region TBD employees.
  const regionCounts = React.useMemo(
    () =>
      Object.entries(breakdowns.data?.headcount_by_region ?? {}).map(
        ([region, count]) => ({ region, count }),
      ),
    [breakdowns.data],
  )

  return (
    <div className="space-y-5">
      <FilterBar filters={filterDefs} values={filters} onChange={setFilter} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <KpiCard
          label="Total Employees"
          value={totalEmployees ?? '—'}
          loading={isLoading}
          icon={Users}
          iconTone="blue"
        />
        <KpiCard
          label="Active Employees"
          value={activeEmployees ?? '—'}
          loading={isLoading}
          icon={UserCheck}
          iconTone="emerald"
        />
        <KpiCard
          label="Inactive Employees"
          value={inactiveEmployees ?? '—'}
          loading={isLoading}
          icon={UserX}
          iconTone="red"
        />
        <KpiCard
          label="Strategic Pool"
          value={breakdowns.data?.strategic_pool ?? '—'}
          loading={breakdowns.isLoading}
          icon={Target}
          iconTone="blue"
          provisional
        />
        <KpiCard
          label="Departments"
          value={departmentsCount ?? '—'}
          loading={isLoading}
          icon={Building2}
          iconTone="blue"
        />
        <KpiCard
          label="Projects"
          value={projectsCount ?? '—'}
          loading={isLoading}
          icon={Briefcase}
          iconTone="blue"
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <ChartCard
          title="Headcount by Seniority"
          isLoading={isLoading}
          isError={isError}
          isEmpty={seniorityData.length === 0}
          height="h-80"
          provisional
        >
          {/* 9 rows in a fixed h-80 box reads tight — `rowHeightPx` gives
              each bar a fixed height and lets CustomBarChart scroll its
              plot internally (axis titles stay put) instead. */}
          <CustomBarChart
            data={seniorityData}
            index="name"
            category="value"
            color="emerald"
            tooltipValueLabel="Employees"
            layout="vertical"
            yAxisLabel="Seniority"
            xAxisLabel="Employees"
            yAxisWidth={220}
            rowHeightPx={32}
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Workforce by Type"
          subtitle="GCC vs Non GCC"
          isLoading={isLoading}
          isError={isError}
          isEmpty={typeData.length === 0}
          height="h-80"
        >
          <CustomDonutChart data={typeData} colors={typeColors} className="h-full" />

        </ChartCard>
      </div>

      <div className="grid grid-cols-1 items-start gap-4">
        <ChartCard
          title="Workforce Details by Region"
          subtitle="Total headcount per region"
          isLoading={isLoading}
          isError={isError}
          isEmpty={regionCounts.every((r) => r.count === 0)}
          height="h-96 sm:h-80"
        >
          {/* Single column on mobile — a hard-coded 2x2 grid squeezed each
              region's label + progress bar + count into a ~150px-wide
              column on a narrow phone, the one non-adaptive layout on this
              page. `sm:grid-rows-2` (not a bare `grid-rows-2`) matters
              too: locking 2 rows while still `grid-cols-1` below `sm`
              would push the 3rd/4th items into implicit rows the fixed
              card height can't account for. */}
          <div className="grid h-full grid-cols-1 gap-3 sm:grid-cols-2 sm:grid-rows-2">
            {regionCounts.map(({ region, count }) => {
              const maxCount = Math.max(...regionCounts.map((r) => r.count), 1)
              const widthPct = Math.max((count / maxCount) * 100, count > 0 ? 6 : 0)
              return (
                <div
                  key={region}
                  className="flex flex-col justify-center gap-2 rounded-xl border border-border p-3"
                >
                  <p className="text-xs font-medium text-muted-foreground">{region}</p>
                  <div className="flex items-center gap-2">
                    <div className="h-6 flex-1 overflow-hidden rounded bg-tremor-background-subtle dark:bg-dark-tremor-background-subtle">
                      <div
                        className="h-full rounded bg-primary transition-all"
                        style={{ width: `${widthPct}%` }}
                      />
                    </div>
                    <p className="w-8 text-right text-sm font-semibold tabular-nums">{count}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </ChartCard>
      </div>
    </div>
  )
}
