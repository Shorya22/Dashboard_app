import * as React from 'react'
import { Users, Briefcase, Building2, UserCheck } from 'lucide-react'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { FilterBar } from '@/components/dashboard/filter-bar'
import { CustomDonutChart } from '@/components/dashboard/custom-donut-chart'
import { CustomBarChart } from '@/components/dashboard/custom-bar-chart'
import { useRosterEmployeesAll } from '@/lib/roster-api'
import { STATUS_COLORS, colorsForLabels } from '@/lib/chart-colors'
import { withTruncatedLabels } from '@/lib/chart-labels'
import {
  ALL,
  applyEmployeeFilters,
  buildOptions,
  deriveExperienceBand,
  distinctDepartmentsCount,
  distinctValues,
  groupCount,
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

  // Memoized: charts on this page are React.memo'd (custom-bar-chart.tsx /
  // custom-donut-chart.tsx), so stable references here avoid redrawing all
  // 4 charts whenever this page re-renders for an unrelated reason.
  const filtered = React.useMemo(
    () =>
      applyEmployeeFilters(employees, filters, {
        region: 'region',
        status: 'status',
        department: 'designation',
      }),
    [employees, filters],
  )

  const totalEmployees = filtered.length
  const activeEmployees = filtered.filter((e) => e.status === 'Active').length
  const departmentsCount = distinctDepartmentsCount(filtered)
  // Projects mirrors the real DAX's naive DISTINCTCOUNT over the raw,
  // messy `Client as on June 2026` string field (see data-model skill) —
  // replicated here, not "fixed" to a per-client count.
  const projectsCount = distinctValues(filtered, 'client').length

  const statusData = React.useMemo(
    () =>
      Object.entries(groupCount(filtered.map((e) => e.status ?? 'Unknown'))).map(
        ([name, value]) => ({ name, value }),
      ),
    [filtered],
  )
  const statusColors = React.useMemo(
    () => colorsForLabels(statusData.map((d) => d.name), STATUS_COLORS),
    [statusData],
  )

  const regionData = React.useMemo(
    () =>
      withTruncatedLabels(
        Object.entries(groupCount(filtered.map((e) => e.region ?? 'Region TBD'))).map(
          ([name, value]) => ({ name, value }),
        ),
        'name',
      ),
    [filtered],
  )

  const entityData = React.useMemo(
    () =>
      withTruncatedLabels(
        Object.entries(
          groupCount(filtered.map((e) => e.working_entity ?? 'Entity TBD')),
        ).map(([name, value]) => ({ name, value })),
        'name',
      ),
    [filtered],
  )
  // Working Entity has 8 distinct real values (AMER, DTAU, DTDE, DTIE,
  // DTNL, DTUK, Entity TBD, Hexaware) — above the dashboard-design skill's
  // 4-5 segment cap for donuts, so a bar chart is the CORRECT choice per
  // our own chart-type rule, even though the Power BI reference PDF shows
  // a donut for this metric. Keeping the bar chart; the reference is the
  // inconsistent one here.
  const entitySegmentCount = distinctValues(employees, 'working_entity').length

  const experienceBandData = React.useMemo(
    () =>
      withTruncatedLabels(
        Object.entries(
          groupCount(filtered.map((e) => deriveExperienceBand(e.total_experience))),
        ).map(([name, value]) => ({ name, value })),
        'name',
      ),
    [filtered],
  )

  const isLoading = employeesQuery.isLoading
  const isError = employeesQuery.isError

  return (
    <div className="space-y-5">
      <FilterBar filters={filterDefs} values={filters} onChange={setFilter} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total Employees"
          value={isLoading ? '—' : totalEmployees}
          loading={isLoading}
          icon={Users}
          iconTone="blue"
        />
        <KpiCard
          label="Departments"
          value={isLoading ? '—' : departmentsCount}
          loading={isLoading}
          icon={Building2}
          iconTone="blue"
        />
        <KpiCard
          label="Projects"
          value={isLoading ? '—' : projectsCount}
          loading={isLoading}
          icon={Briefcase}
          iconTone="blue"
        />
        <KpiCard
          label="Active Employees"
          value={isLoading ? '—' : activeEmployees}
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
