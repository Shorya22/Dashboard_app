import * as React from 'react'
import { Users, BookOpen, Building2 } from 'lucide-react'
import { CustomBarChart } from '@/components/dashboard/custom-bar-chart'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { FilterBar } from '@/components/dashboard/filter-bar'
import {
  useRosterBreakdowns,
  useRosterEmployeesAll,
  useRosterSkills,
  useRosterSummary,
} from '@/lib/roster-api'
import { colorsForLabels, EXPERIENCE_BAND_COLORS, REGION_COLORS, SENIORITY_CATEGORY_COLORS } from '@/lib/chart-colors'
import { withTruncatedLabels } from '@/lib/chart-labels'
import {
  ALL,
  buildOptions,
  distinctNormalizedValues,
  distinctValues,
  normalizePrimarySkillLabel,
  type FilterValues,
} from '@/lib/employee-filters'

/** Pivots a filtered employee list into one row per Primary Skill with one
 * numeric column per distinct value of `groupFn`, the shape Tremor's
 * stacked BarChart expects. Computed entirely client-side from the
 * filtered employee list (not the pre-aggregated /roster/skills endpoint)
 * so all 6 filter dropdowns propagate to every chart on this page. */
/** Reshape the server's long cross-tab rows into the wide form the stacked
 * bar chart wants. Pure reshaping — the bucketing itself (experience bands,
 * seniority categories) is done server-side from the YAML definitions, so
 * this file no longer holds a second copy of those rules. */
function pivotLongRows<T extends { primary_skill: string; count: number }>(
  rows: T[],
  groupKey: keyof T,
): { data: Record<string, number | string>[]; groups: string[] } {
  const skills = Array.from(new Set(rows.map((r) => r.primary_skill)))
  const groups = Array.from(new Set(rows.map((r) => String(r[groupKey]))))
  const data = skills.map((skill) => {
    const row: Record<string, number | string> = { primary_skill: skill }
    for (const g of groups) {
      row[g] = rows
        .filter((r) => r.primary_skill === skill && String(r[groupKey]) === g)
        .reduce((sum, r) => sum + r.count, 0)
    }
    return row
  })
  return { data: withTruncatedLabels(data, 'primary_skill'), groups }
}

export function SkillsExperiencePage() {
  // Unfiltered list, used ONLY to populate the filter dropdowns — if it
  // followed the filters, picking one would erase the other options.
  const allEmployeesQuery = useRosterEmployeesAll()
  const employees = React.useMemo(
    () => allEmployeesQuery.data?.items ?? [],
    [allEmployeesQuery.data],
  )

  const [filters, setFilters] = React.useState<FilterValues>({
    region: ALL,
    department: ALL,
    skill: ALL,
    experience: ALL,
    seniorityCategory: ALL,
    type: ALL,
  })
  const setFilter = (key: string, value: string) =>
    setFilters((prev) => ({ ...prev, [key]: value }))

  // Everything on this page comes from the server WITH the filters applied,
  // so it uses the single YAML definitions. The experience bands and
  // seniority categories used to be re-derived here in JavaScript
  // (deriveExperienceBand / deriveSeniorityCategory) — a second copy of the
  // thresholds that had to be kept in step with config by hand.
  const serverFilters = React.useMemo(() => {
    const out: Record<string, string | undefined> = {}
    for (const [key, value] of Object.entries(filters)) {
      out[key] = value === ALL ? undefined : value
    }
    return out
  }, [filters])
  const summaryQuery = useRosterSummary(serverFilters)
  const skillsQuery = useRosterSkills(serverFilters)
  const employeesQuery = useRosterEmployeesAll(serverFilters)

  // Option lists come from the server's own bucket labels, so the choices a
  // user sees are exactly the buckets the charts draw. Deriving them here
  // was the last JS copy of the band rules on this page.
  const allBreakdowns = useRosterBreakdowns()
  const experienceOptions = Object.keys(
    allBreakdowns.data?.workforce_by_experience_band ?? {},
  )
  const seniorityCategoryOptions = Object.keys(
    allBreakdowns.data?.workforce_by_seniority_category ?? {},
  )

  const filterDefs = [
    { key: 'region', label: 'Region/Market', options: buildOptions(distinctValues(employees, 'region')) },
    {
      key: 'department',
      label: 'Department',
      options: buildOptions(distinctValues(employees, 'designation')),
    },
    {
      key: 'skill',
      label: 'Primary Skill',
      options: buildOptions(
        distinctNormalizedValues(employees, 'primary_skill', normalizePrimarySkillLabel),
      ),
    },
    { key: 'experience', label: 'Experience', options: buildOptions(experienceOptions) },
    {
      key: 'seniorityCategory',
      label: 'Seniority Category',
      options: buildOptions(seniorityCategoryOptions),
    },
    { key: 'type', label: 'Type', options: buildOptions(distinctValues(employees, 'type')) },
  ]

  // Memoized: this page's 4 charts are React.memo'd (custom-bar-chart.tsx),
  // so stable references here mean an unrelated re-render doesn't force
  // every chart to redraw.
  const isLoading =
    employeesQuery.isLoading || summaryQuery.isLoading || skillsQuery.isLoading
  const isError = employeesQuery.isError || summaryQuery.isError || skillsQuery.isError


  // The server returns these cross-tabs already bucketed with the filters
  // applied, so the page only reshapes long rows into the chart's wide
  // form. It used to bucket them here with JS copies of the band rules.
  const byExperience = React.useMemo(
    () =>
      pivotLongRows(
        skillsQuery.data?.skill_bifurcation_by_experience_band ?? [],
        'experience_band',
      ),
    [skillsQuery.data],
  )
  const bySeniority = React.useMemo(
    () =>
      pivotLongRows(
        skillsQuery.data?.skill_bifurcation_by_seniority_category ?? [],
        'seniority_category',
      ),
    [skillsQuery.data],
  )
  const byRegion = React.useMemo(
    () => pivotLongRows(skillsQuery.data?.skill_bifurcation_by_region ?? [], 'region'),
    [skillsQuery.data],
  )

  const byExperienceSeries = React.useMemo(
    () =>
      byExperience.groups.map((category: string) => ({
        category,
        color: colorsForLabels([category], EXPERIENCE_BAND_COLORS)[0],
      })),
    [byExperience],
  )
  const bySenioritySeries = React.useMemo(
    () =>
      bySeniority.groups.map((category: string) => ({
        category,
        color: colorsForLabels([category], SENIORITY_CATEGORY_COLORS)[0],
      })),
    [bySeniority],
  )
  const byRegionSeries = React.useMemo(
    () => byRegion.groups.map((category: string) => ({ category, color: colorsForLabels([category], REGION_COLORS)[0] })),
    [byRegion],
  )

  const experienceBandData = React.useMemo(() => {
    const totals: Record<string, number> = {}
    for (const row of skillsQuery.data?.skill_bifurcation_by_experience_band ?? []) {
      totals[row.experience_band] = (totals[row.experience_band] ?? 0) + row.count
    }
    return withTruncatedLabels(
      Object.entries(totals).map(([name, value]) => ({ name, value })),
      'name',
    )
  }, [skillsQuery.data])

  const totalEmployees = summaryQuery.data?.total_employees
  const departmentsCount = summaryQuery.data?.departments
  // Confirmed real DAX measure — now always the server's value, filtered
  // or not, instead of being recomputed client-side once a filter was set.
  const skillsCovered = summaryQuery.data?.skills_covered

  return (
    <div className="space-y-5">
      <FilterBar filters={filterDefs} values={filters} onChange={setFilter} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard
          label="Total Employees"
          value={totalEmployees ?? '—'}
          loading={isLoading}
          icon={Users}
          iconTone="blue"
        />
        <KpiCard
          label="Skills Covered"
          value={skillsCovered ?? '—'}
          loading={summaryQuery.isLoading}
          icon={BookOpen}
          iconTone="blue"
        />
        <KpiCard
          label="Departments"
          value={departmentsCount ?? '—'}
          loading={isLoading}
          icon={Building2}
          iconTone="blue"
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <ChartCard
          title="Skill Bifurcation by Experience"
          isLoading={isLoading}
          isError={isError}
          isEmpty={byExperience.data.length === 0}
          height="h-80"
          provisional
          provisionalNote="Experience Band bucket boundaries are PROVISIONAL, see the data-model skill."
        >
          {/* One horizontal bar per distinct Primary Skill (often 15-20+)
              inside a fixed h-80 box would squeeze every bar to a few px
              tall on mobile — unreadable. `rowHeightPx` gives each bar a
              fixed height and lets CustomBarChart scroll its plot
              internally (axis titles stay put) instead. */}
          <CustomBarChart
            data={byExperience.data}
            index="primary_skill"
            series={byExperienceSeries}
            stack
            layout="vertical"
            yAxisWidth={110}
            yAxisLabel="Primary Skill"
            xAxisLabel="Employees"
            showLegend
            tooltipValueLabel="Employees"
            rowHeightPx={32}
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Skill Bifurcation by Seniority"
          isLoading={isLoading}
          isError={isError}
          isEmpty={bySeniority.data.length === 0}
          height="h-80"
          provisional
          provisionalNote="Seniority Category mapping is PROVISIONAL, see the data-model skill."
        >
          <CustomBarChart
            data={bySeniority.data}
            index="primary_skill"
            series={bySenioritySeries}
            stack
            layout="vertical"
            yAxisWidth={110}
            yAxisLabel="Primary Skill"
            xAxisLabel="Employees"
            showLegend
            tooltipValueLabel="Employees"
            rowHeightPx={32}
            className="h-full"
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <ChartCard
          title="Skill Bifurcation by Region"
          isLoading={isLoading}
          isError={isError}
          isEmpty={byRegion.data.length === 0}
          height="h-80"
        >
          <CustomBarChart
            data={byRegion.data}
            index="primary_skill"
            series={byRegionSeries}
            stack
            layout="vertical"
            yAxisWidth={110}
            yAxisLabel="Primary Skill"
            xAxisLabel="Employees"
            showLegend
            tooltipValueLabel="Employees"
            rowHeightPx={32}
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Total Employees by Experience Band"
          isLoading={isLoading}
          isError={isError}
          isEmpty={experienceBandData.length === 0}
          height="h-80"
          provisional
          provisionalNote="Experience Band bucket boundaries are PROVISIONAL, see the data-model skill."
        >
          <CustomBarChart
            data={experienceBandData}
            index="name"
            category="value"
            color="terracotta"
            yAxisLabel="Employees"
            xAxisLabel="Experience Band"
            showLegend={false}
            tooltipValueLabel="Employees"
            className="h-full"
          />
        </ChartCard>
      </div>
    </div>
  )
}
