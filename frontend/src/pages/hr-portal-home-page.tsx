import * as React from 'react'
import { Users, Briefcase, Building2, UserCheck } from 'lucide-react'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { FilterBar } from '@/components/dashboard/filter-bar'
import { CustomDonutChart } from '@/components/dashboard/custom-donut-chart'
import { CustomBarChart } from '@/components/dashboard/custom-bar-chart'
import { useRosterBreakdowns, useRosterEmployeesAll, useRosterSummary } from '@/lib/roster-api'
import { STATUS_COLORS, colorsForLabels } from '@/lib/chart-colors'
import { withTruncatedLabels } from '@/lib/chart-labels'
import {
  ALL,
  buildOptions,
  buildServerFilters,
  distinctValues,
  type FilterValues,
} from '@/lib/employee-filters'

// This page's KPIs and all 4 charts are recomputed client-side from the
// full employee list (see lib/employee-filters.ts) so the Region/Status/
// Department filters below actually propagate everywhere, not just to the
// dropdowns — the /roster/summary and /roster/breakdowns endpoints don't
// accept filter query params, and the roster is small enough (52 rows)
// that this is cheap. Any date-based measure (Strategic Pool, Closing
// Headcount) is out of scope here since EmployeeRecord doesn't expose
// DOJ/LWD — this page doesn't show any of those, so it isn't an issue yet.

export function HrPortalHomePage() {
  const employeesQuery = useRosterEmployeesAll()
  const employees = React.useMemo(() => employeesQuery.data?.items ?? [], [employeesQuery.data])

  const [filters, setFilters] = React.useState<FilterValues>({
    region: ALL,
    status: ALL,
    department: ALL,
  })
  const setFilter = (key: string, value: string) =>
    setFilters((prev) => ({ ...prev, [key]: value }))

  const filterDefs = [
    {
      key: 'region',
      label: 'Region/Market',
      options: buildOptions(distinctValues(employees, 'region')),
    },
    {
      key: 'status',
      label: 'Status',
      options: buildOptions(distinctValues(employees, 'status')),
    },
    {
      key: 'department',
      label: 'Department',
      options: buildOptions(distinctValues(employees, 'designation')),
    },
  ]


  // KPIs come from the server WITH this page's filters applied, so they use
  // the single YAML metric definitions. Recomputing them here meant
  // hardcoding "Active" in the browser and counting ROWS for Total
  // Employees where the definition is distinct employee ids — two silent
  // ways to drift from the backend.
  const serverFilters = React.useMemo(
    () => buildServerFilters(filters),
    [filters],
  )
  const summary = useRosterSummary(serverFilters)
  const breakdowns = useRosterBreakdowns(serverFilters)
  const totalEmployees = summary.data?.total_employees
  const activeEmployees = summary.data?.active_employees
  const departmentsCount = summary.data?.departments
  const projectsCount = summary.data?.projects

  // Charts come from the server WITH this page's filters applied, exactly
  // like the KPIs above. They used to be regrouped here from the filtered
  // rows, which re-implemented the definitions in the browser: the
  // experience bands were a second hardcoded copy of the YAML thresholds
  // (deriveExperienceBand), and the blank labels ("Region TBD", "Entity
  // TBD") were hardcoded strings that had to be kept in step with config
  // by hand. Now there is one definition and the two can't disagree.
  const toChartData = (counts: Record<string, number> | undefined) =>
    Object.entries(counts ?? {}).map(([name, value]) => ({ name, value }))

  const statusData = React.useMemo(
    () => toChartData(breakdowns.data?.status_split),
    [breakdowns.data],
  )
  const statusColors = React.useMemo(
    () => colorsForLabels(statusData.map((d) => d.name), STATUS_COLORS),
    [statusData],
  )

  const regionData = React.useMemo(
    () => withTruncatedLabels(toChartData(breakdowns.data?.headcount_by_region), 'name'),
    [breakdowns.data],
  )

  const entityData = React.useMemo(
    () =>
      withTruncatedLabels(
        toChartData(breakdowns.data?.workforce_by_working_entity),
        'name',
      ),
    [breakdowns.data],
  )
  // Working Entity has more distinct values than the dashboard-design
  // skill's 4-5 segment cap for donuts, so a bar chart is the correct
  // choice per our own chart-type rule, even though the Power BI reference
  // PDF shows a donut. Keeping the bar chart; the reference is the
  // inconsistent one here.
  const entitySegmentCount = entityData.length

  const experienceBandData = React.useMemo(
    () =>
      withTruncatedLabels(
        toChartData(breakdowns.data?.workforce_by_experience_band),
        'name',
      ),
    [breakdowns.data],
  )

  const isLoading = employeesQuery.isLoading || summary.isLoading || breakdowns.isLoading
  const isError = employeesQuery.isError

  return (
    <div className="space-y-5">
      <FilterBar filters={filterDefs} values={filters} onChange={setFilter} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total Employees"
          value={totalEmployees ?? '—'}
          loading={isLoading}
          icon={Users}
          iconTone="blue"
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
        <KpiCard
          label="Active Employees"
          value={activeEmployees ?? '—'}
          loading={isLoading}
          icon={UserCheck}
          iconTone="emerald"
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <ChartCard
          title="Status Split"
          subtitle="Active vs Inactive vs Strategic Pool"
          isLoading={isLoading}
          isError={isError}
          isEmpty={statusData.length === 0}
        >
          <CustomDonutChart data={statusData} colors={statusColors} className="h-full" />
        </ChartCard>

        <ChartCard
          title="Headcount by Region"
          isLoading={isLoading}
          isError={isError}
          isEmpty={regionData.length === 0}
        >
          <CustomBarChart
            data={regionData}
            index="name"
            category="value"
            color="teal"
            tooltipValueLabel="Employees"
            yAxisLabel="Employees"
            xAxisLabel="Region"
            className="h-full"
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <ChartCard
          title="Workforce by Working Entity"
          subtitle={`${entitySegmentCount} entities — bar chart, not a donut, since that exceeds the design skill's 4-5 segment cap for part-to-whole circles`}
          isLoading={isLoading}
          isError={isError}
          isEmpty={entityData.length === 0}
        >
          <CustomBarChart
            data={entityData}
            index="name"
            category="value"
            color="violet"
            tooltipValueLabel="Employees"
            layout="vertical"
            yAxisLabel="Entity"
            xAxisLabel="Employees"
            yAxisWidth={110}
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Workforce by Experience Band"
          isLoading={isLoading}
          isError={isError}
          isEmpty={experienceBandData.length === 0}
          provisional
          provisionalNote="Experience Band bucket boundaries are PROVISIONAL, not yet confirmed against the real Power BI DAX. See the data-model skill."
        >
          <CustomBarChart
            data={experienceBandData}
            index="name"
            category="value"
            color="amber"
            tooltipValueLabel="Employees"
            yAxisLabel="Employees"
            xAxisLabel="Experience Band"
            className="h-full"
          />
        </ChartCard>
      </div>
    </div>
  )
}
