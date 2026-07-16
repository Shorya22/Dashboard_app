import * as React from 'react'
import { BarChart } from '@tremor/react'
import { Users, BookOpen, Building2 } from 'lucide-react'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { ChartCard } from '@/components/dashboard/chart-states'
import { FilterBar } from '@/components/dashboard/filter-bar'
import {
  createFullLabelTooltip,
  FullLabelTooltip,
} from '@/components/dashboard/full-label-tooltip'
import { useRosterEmployeesAll, useRosterSummary, type EmployeeRecord } from '@/lib/roster-api'
import { colorsForLabels } from '@/lib/chart-colors'
import { withTruncatedLabels } from '@/lib/chart-labels'
import {
  ALL,
  applyEmployeeFilters,
  buildOptions,
  deriveExperienceBand,
  deriveSeniorityCategory,
  distinctDepartmentsCount,
  distinctNormalizedValues,
  distinctSkillsCoveredCount,
  distinctValues,
  groupCount,
  normalizePrimarySkillLabel,
  type FilterValues,
} from '@/lib/employee-filters'

const employeesTooltip = createFullLabelTooltip('Employees')

/** Pivots a filtered employee list into one row per Primary Skill with one
 * numeric column per distinct value of `groupFn`, the shape Tremor's
 * stacked BarChart expects. Computed entirely client-side from the
 * filtered employee list (not the pre-aggregated /roster/skills endpoint)
 * so all 6 filter dropdowns propagate to every chart on this page. */
function pivotBySkill(
  employees: EmployeeRecord[],
  groupFn: (e: EmployeeRecord) => string,
): { data: Record<string, number | string>[]; groups: string[] } {
  // Primary Skill has a casing-duplicate data-quality issue ("React JS" vs
  // "React Js") — normalize before grouping so the two variants collapse
  // into a single Y-axis category, same treatment as Designation.
  const withSkill = employees
    .filter((e) => e.primary_skill)
    .map((e) => ({ ...e, primary_skill: normalizePrimarySkillLabel(e.primary_skill as string) }))
  const skills = Array.from(new Set(withSkill.map((e) => e.primary_skill as string)))
  const groups = Array.from(new Set(withSkill.map(groupFn)))
  const data = skills.map((skill) => {
    const row: Record<string, number | string> = { primary_skill: skill }
    groups.forEach((g) => {
      row[g] = withSkill.filter((e) => e.primary_skill === skill && groupFn(e) === g).length
    })
    return row
  })
  return { data: withTruncatedLabels(data, 'primary_skill'), groups }
}

export function SkillsExperiencePage() {
  const employeesQuery = useRosterEmployeesAll()
  const summaryQuery = useRosterSummary()
  const employees = employeesQuery.data?.items ?? []

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

  const experienceOptions = Array.from(
    new Set(employees.map((e) => deriveExperienceBand(e.total_experience))),
  ).sort()
  const seniorityCategoryOptions = Array.from(
    new Set(employees.map((e) => deriveSeniorityCategory(e.seniority_level))),
  ).sort()

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

  const baseFiltered = applyEmployeeFilters(
    employees,
    filters,
    {
      region: 'region',
      department: 'designation',
      skill: 'primary_skill',
      type: 'type',
    },
    { skill: normalizePrimarySkillLabel },
  )
  // experience / seniorityCategory are derived fields, not raw
  // EmployeeRecord columns, so they're applied as an extra manual pass
  // rather than through applyEmployeeFilters's direct field map.
  const filtered = baseFiltered.filter((e) => {
    if (filters.experience !== ALL && deriveExperienceBand(e.total_experience) !== filters.experience) {
      return false
    }
    if (
      filters.seniorityCategory !== ALL &&
      deriveSeniorityCategory(e.seniority_level) !== filters.seniorityCategory
    ) {
      return false
    }
    return true
  })

  const isLoading = employeesQuery.isLoading
  const isError = employeesQuery.isError

  const isUnfiltered = Object.values(filters).every((v) => v === ALL)
  const skillsCoveredLoading = isUnfiltered ? summaryQuery.isLoading : isLoading

  const byExperience = pivotBySkill(filtered, (e) => deriveExperienceBand(e.total_experience))
  const bySeniority = pivotBySkill(filtered, (e) => deriveSeniorityCategory(e.seniority_level))
  const byRegion = pivotBySkill(filtered, (e) => e.region ?? 'Region TBD')

  const experienceBandData = withTruncatedLabels(
    Object.entries(groupCount(filtered.map((e) => deriveExperienceBand(e.total_experience)))).map(
      ([name, value]) => ({ name, value }),
    ),
    'name',
  )

  const totalEmployees = filtered.length
  const departmentsCount = distinctDepartmentsCount(filtered)
  // Confirmed real DAX measure (`get_skills_covered`, DISTINCTCOUNT of the
  // `Skill` column excluding blank/TBD-containing values). Unfiltered
  // default reads the backend's `/roster/summary.skills_covered` directly
  // (16); once a filter is applied, recomputed client-side from the
  // filtered list's `skill` field with the same exclusion rules so the KPI
  // stays filter-reactive per the dashboard-design filter-propagation rule.
  const skillsCovered = isUnfiltered
    ? summaryQuery.data?.skills_covered
    : distinctSkillsCoveredCount(filtered)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Skills &amp; Experience
        </h1>
        <p className="text-sm text-muted-foreground">
          Skill mix by experience, seniority, and region
        </p>
      </div>

      <FilterBar filters={filterDefs} values={filters} onChange={setFilter} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard
          label="Total Employees"
          value={isLoading ? '—' : totalEmployees}
          loading={isLoading}
          icon={Users}
          iconTone="blue"
        />
        <KpiCard
          label="Skills Covered"
          value={skillsCoveredLoading ? '—' : (skillsCovered ?? '—')}
          loading={skillsCoveredLoading}
          icon={BookOpen}
          iconTone="blue"
        />
        <KpiCard
          label="Departments"
          value={isLoading ? '—' : departmentsCount}
          loading={isLoading}
          icon={Building2}
          iconTone="orange"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          title="Skill Bifurcation by Experience"
          isLoading={isLoading}
          isError={isError}
          isEmpty={byExperience.data.length === 0}
          height="h-96"
          provisional
          provisionalNote="Experience Band bucket boundaries are PROVISIONAL, see the data-model skill."
        >
          <BarChart
            data={byExperience.data}
            index="primary_skill"
            categories={byExperience.groups}
            colors={colorsForLabels(byExperience.groups)}
            layout="vertical"
            yAxisWidth={110}
            xAxisLabel="Employees"
            showLegend
            stack
            customTooltip={FullLabelTooltip}
            showAnimation
            animationDuration={1000}
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Skill Bifurcation by Seniority"
          isLoading={isLoading}
          isError={isError}
          isEmpty={bySeniority.data.length === 0}
          height="h-96"
          provisional
          provisionalNote="Seniority Category mapping is PROVISIONAL, see the data-model skill."
        >
          <BarChart
            data={bySeniority.data}
            index="primary_skill"
            categories={bySeniority.groups}
            colors={colorsForLabels(bySeniority.groups)}
            layout="vertical"
            yAxisWidth={110}
            xAxisLabel="Employees"
            showLegend
            stack
            customTooltip={FullLabelTooltip}
            showAnimation
            animationDuration={1000}
            className="h-full"
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          title="Skill Bifurcation by Region"
          isLoading={isLoading}
          isError={isError}
          isEmpty={byRegion.data.length === 0}
          height="h-96"
        >
          <BarChart
            data={byRegion.data}
            index="primary_skill"
            categories={byRegion.groups}
            colors={colorsForLabels(byRegion.groups)}
            layout="vertical"
            yAxisWidth={110}
            xAxisLabel="Employees"
            showLegend
            stack
            customTooltip={FullLabelTooltip}
            showAnimation
            animationDuration={1000}
            className="h-full"
          />
        </ChartCard>

        <ChartCard
          title="Total Employees by Experience Band"
          isLoading={isLoading}
          isError={isError}
          isEmpty={experienceBandData.length === 0}
          height="h-96"
          provisional
          provisionalNote="Experience Band bucket boundaries are PROVISIONAL, see the data-model skill."
        >
          <BarChart
            data={experienceBandData}
            index="name"
            categories={['value']}
            colors={['orange']}
            yAxisLabel="Employees"
            xAxisLabel="Experience Band"
            showLegend={false}
            customTooltip={employeesTooltip}
            showAnimation
            animationDuration={1000}
            className="h-full"
          />
        </ChartCard>
      </div>
    </div>
  )
}
