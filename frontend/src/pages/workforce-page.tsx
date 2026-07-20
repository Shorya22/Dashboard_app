import * as React from 'react'
import { Users, UserCheck, UserX, Target, Building2, Briefcase } from 'lucide-react'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { FilterBar } from '@/components/dashboard/filter-bar'
import { CustomBarChart } from '@/components/dashboard/custom-bar-chart'
import { CustomDonutChart } from '@/components/dashboard/custom-donut-chart'
import { useRosterBreakdowns, useRosterEmployeesAll } from '@/lib/roster-api'
import { withTruncatedLabels } from '@/lib/chart-labels'
import { TYPE_COLORS, colorsForLabels } from '@/lib/chart-colors'
import {
  ALL,
  applyEmployeeFilters,
  buildOptions,
  distinctDepartmentsCount,
  distinctValues,
  groupCount,
  type FilterValues,
} from '@/lib/employee-filters'

const REGION_QUADRANTS = ['AMER', 'APAC', 'EMEA', 'Hexaware'] as const

/** Mirrors the backend's `_normalize_seniority_label` (roster_metrics.py)
 * exactly: casing-duplicate `Seniorirty Level` source values (confirmed:
 * "Premium Lead"/"Premium lead", "Standard Senior"/"Standard senior")
 * collapse into one title-cased label instead of splitting a single
 * logical category into two bars. Without this, the client-side
 * recompute (needed so filters propagate, since /roster/breakdowns takes
 * no filter params) produced 11 raw categories instead of 9, and Tremor's
 * BarChart silently thinned its Y-axis ticks to fit — the chart looked
 * like it had only 6 categories even though ~11 bars were actually
 * rendered. Normalizing here fixes the category count at the source. */
function normalizeSeniorityLabel(value: string): string {
  const titleCased = value
    .trim()
    .split(' ')
    .map((word) => (word ? word[0].toUpperCase() + word.slice(1).toLowerCase() : word))
    .join(' ')
  return titleCased.replace(/Tbd/g, 'TBD')
}

export function WorkforcePage() {
  
  const breakdowns = useRosterBreakdowns()
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
  const filtered = React.useMemo(
    () =>
      applyEmployeeFilters(employees, filters, {
        region: 'region',
        grade: 'grade',
        department: 'designation',
        skill: 'primary_skill',
      }),
    [employees, filters],
  )
  const isLoading = employeesQuery.isLoading
  const isError = employeesQuery.isError

  const totalEmployees = filtered.length
  const activeEmployees = filtered.filter((e) => e.status === 'Active').length
  const inactiveEmployees = filtered.filter((e) => e.status === 'Inactive').length
  const departmentsCount = distinctDepartmentsCount(filtered)
  const projectsCount = distinctValues(filtered, 'client').length

  const seniorityData = React.useMemo(
    () =>
      withTruncatedLabels(
        Object.entries(
          groupCount(
            filtered.map((e) => normalizeSeniorityLabel(e.seniority_level ?? 'Seniority TBD')),
          ),
        )
          .map(([name, value]) => ({ name, value }))
          .sort((a, b) => b.value - a.value),
        'name',
      ),
    [filtered],
  )

  const typeData = React.useMemo(
    () =>
      Object.entries(groupCount(filtered.map((e) => e.type ?? 'Type TBD')))
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => (a.name === 'GCC' ? -1 : b.name === 'GCC' ? 1 : 0)),
    [filtered],
  )
  const typeColors = React.useMemo(
    () =>
      colorsForLabels(
        typeData.map((d) => d.name),
        TYPE_COLORS,
      ),
    [typeData],
  )

  const regionCounts = REGION_QUADRANTS.map((region) => ({
    region,
    count: filtered.filter((e) => e.region === region).length,
  }))

  return (
    <div className="space-y-5">
      <FilterBar filters={filterDefs} values={filters} onChange={setFilter} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <KpiCard
          label="Total Employees"
          value={isLoading ? '—' : totalEmployees}
          loading={isLoading}
          icon={Users}
          iconTone="blue"
        />
        <KpiCard
          label="Active Employees"
          value={isLoading ? '—' : activeEmployees}
          loading={isLoading}
          icon={UserCheck}
          iconTone="emerald"
        />
        <KpiCard
          label="Inactive Employees"
          value={isLoading ? '—' : inactiveEmployees}
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
          provisionalNote="Not affected by the filters above — Strategic Pool is date-based (ISBLANK(DOJ (DEPT))) and DOJ (DEPT) isn't exposed by /roster/employees, so it can't be recomputed client-side. Shows the global, unfiltered value."
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
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <ChartCard
          title="Headcount by Seniority"
          isLoading={isLoading}
          isError={isError}
          isEmpty={seniorityData.length === 0}
          height="h-80"
          provisional
          provisionalNote="Recomputed client-side from the raw Seniorirty Level field per selected filters, with the same casing-collapse normalization as the backend's /roster/breakdowns (title-case + TBD restore) applied, so all 9 seniority categories render as 9 distinct bars matching the unfiltered totals."
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
          subtitle="AMER / APAC / EMEA / Hexaware — total headcount per region"
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
