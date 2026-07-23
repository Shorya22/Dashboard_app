// Shared client-side filtering helpers for the HR Portal pages.
//
// The backend's roster endpoints (`/roster/summary`, `/roster/breakdowns`,
// `/roster/skills`) return pre-aggregated numbers/rows and don't accept
// filter query params. Since the full roster is only 52 rows, every
// filterable HR Portal page fetches the full employee list once
// (`useRosterEmployeesAll`, see roster-api.ts) and recomputes KPIs/chart
// data from that filtered list in the browser, instead of re-aggregating
// on the server. This keeps every chart/KPI on a page in sync with the
// same filter state (dashboard-design skill's filter-propagation rule).
//
// Caveat: EmployeeRecord (the /roster/employees row shape) does not expose
// DOJ (DEPT) or LWD, so Strategic Pool / Closing Headcount / Joiners /
// Exits — anything date-based — cannot be recomputed from this list. Pages
// that show those KPIs leave them as the server-computed, unfiltered
// value and say so, rather than silently filtering everything else and
// leaving one KPI inconsistent.

import type { EmployeeRecord } from './roster-api'

export type FilterValues = Record<string, string>
export const ALL = '__all__'

export interface FilterOption {
  label: string
  value: string
}

export interface FilterDef {
  key: string
  label: string
  options: FilterOption[]
}

/**
 * Convert a page's raw filter state into the server query params.
 *
 * Every non-`ALL` filter is passed through by key, so a dropdown can never
 * be shown on a page without also being sent to the API — the class of bug
 * where a filter appears to do nothing. `monthYear` is excluded by default
 * because it filters the time-series charts in the browser, not the roster.
 */
export function buildServerFilters(
  filters: FilterValues,
  exclude: string[] = ['monthYear'],
): Record<string, string | undefined> {
  const out: Record<string, string | undefined> = {}
  for (const [key, value] of Object.entries(filters)) {
    if (exclude.includes(key)) continue
    out[key] = value === ALL ? undefined : value
  }
  return out
}

// --------------------------------------------------------------------------
// Hierarchical (cascading) filters — e.g. Region > Market, Month > Week.
// A parent dropdown narrows a child dropdown to only the child values that
// occur under the selected parent, and changing the parent resets the child.
// --------------------------------------------------------------------------

/** One parent→child dependency in a cascade (e.g. `{ parent: 'region',
 * child: 'market' }`). A chain like Year>Month>Week is expressed as two
 * rules: year→month and month→week. */
export interface CascadeRule {
  parent: string
  child: string
}

/** Build a `parent value → sorted distinct child values` map from records,
 * so a child dropdown can be narrowed to the parent that's selected. Blank
 * parent/child values are skipped. */
export function buildHierarchyMap<T extends object>(
  rows: T[],
  parentField: keyof T,
  childField: keyof T,
): Record<string, string[]> {
  const sets: Record<string, Set<string>> = {}
  for (const row of rows) {
    const p = row[parentField]
    const c = row[childField]
    if (p == null || String(p).trim() === '') continue
    if (c == null || String(c).trim() === '') continue
    ;(sets[String(p)] ??= new Set()).add(String(c))
  }
  const out: Record<string, string[]> = {}
  for (const [p, s] of Object.entries(sets)) out[p] = Array.from(s).sort()
  return out
}

/** Child option values valid for the currently-selected parent. `ALL`
 * (or unset) parent returns the union of every child value, so the child
 * dropdown still lists everything until a parent is chosen. */
export function childOptionsFor(
  map: Record<string, string[]>,
  parentValue: string | undefined,
): string[] {
  if (!parentValue || parentValue === ALL) {
    return Array.from(new Set(Object.values(map).flat())).sort()
  }
  return map[parentValue] ?? []
}

/** Apply a filter change with cascade resets: whenever a parent filter
 * changes, every dependent child (transitively, so Year resets Month AND
 * Week) is reset to `ALL` — otherwise a stale child value would keep
 * filtering to rows that no longer match the new parent. Returns the next
 * filter state; pure, so it drops straight into a `setFilters(prev => …)`. */
export function applyCascade(
  prev: FilterValues,
  key: string,
  value: string,
  rules: CascadeRule[],
): FilterValues {
  const next = { ...prev, [key]: value }
  // Iterate to a fixed point so a chain (year→month→week) fully clears.
  let changed = new Set([key])
  let progressing = true
  while (progressing) {
    progressing = false
    for (const rule of rules) {
      if (changed.has(rule.parent) && next[rule.child] !== ALL) {
        next[rule.child] = ALL
        changed.add(rule.child)
        progressing = true
      }
    }
  }
  return next
}

/** The roster's one cascade: Market nests under Region. Pass to
 * `applyCascade` from a page's `setFilter` so picking a Region resets Market. */
export const REGION_MARKET_CASCADE: CascadeRule[] = [
  { parent: 'region', child: 'market' },
]

/** The paired Region + Market dropdown defs for a roster page. Market's
 * options are narrowed to the selected Region (all markets when Region is
 * `ALL`). Spread these where the old single "Region/Market" def used to be. */
export function regionMarketDefs(
  employees: EmployeeRecord[],
  selectedRegion: string | undefined,
): FilterDef[] {
  const map = buildHierarchyMap(employees, 'region', 'market')
  return [
    {
      key: 'region',
      label: 'Region',
      options: buildOptions(distinctValues(employees, 'region')),
    },
    {
      key: 'market',
      label: 'Market',
      options: buildOptions(childOptionsFor(map, selectedRegion)),
    },
  ]
}

/** Distinct, sorted, non-empty values for a field across a list of employees. */
export function distinctValues(
  employees: EmployeeRecord[],
  field: keyof EmployeeRecord,
): string[] {
  const set = new Set<string>()
  for (const e of employees) {
    const v = e[field]
    if (v !== null && v !== undefined && String(v).trim() !== '') {
      set.add(String(v))
    }
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b))
}

export function buildOptions(values: string[]): FilterOption[] {
  return [{ label: 'All', value: ALL }, ...values.map((v) => ({ label: v, value: v }))]
}

/** Seniority Category derived client-side from the raw `seniority_level`
 * field, mirroring the backend's PROVISIONAL Seniority Category grouping
 * (Senior / Lead / Mid / Other / TBD) — not the confirmed real DAX
 * calculated column. Used only where the aggregated
 * `workforce_by_seniority_category` breakdown can't be re-filtered
 * per-employee (e.g. Employee Directory, Skills & Experience filters). */
export function deriveSeniorityCategory(level: string | null): string {
  if (!level) return 'TBD'
  const l = level.toLowerCase()
  if (l.includes('tbd')) return 'TBD'
  if (l.includes('senior')) return 'Senior'
  if (l.includes('lead')) return 'Lead'
  if (l.includes('mid')) return 'Mid'
  return 'Other'
}

/** Experience Band bucketing, mirroring the backend's PROVISIONAL bucket
 * boundaries (see data-model skill) — used to recompute
 * `workforce_by_experience_band`-shaped data from a filtered employee list. */
export function deriveExperienceBand(exp: number | null): string {
  if (exp == null) return 'Unknown'
  if (exp < 1) return '0-1 Years'
  if (exp < 3) return '1-3 Years'
  if (exp < 5) return '3-5 Years'
  if (exp < 8) return '5-8 Years'
  return '8+ Years'
}

/** Mirrors the backend's `_normalize_designation_label` /
 * `_normalize_seniority_label` (roster_metrics.py) exactly: trim ->
 * title-case each word -> restore "TBD" casing. Casing-duplicate
 * `Designation` source values (e.g. "SalesForce Core Developer" vs
 * "Salesforce Core Developer") must collapse into a single distinct
 * value before counting Departments, or the client-side recompute
 * (needed so the KPI responds to filters, since the aggregated
 * endpoints take no filter params) will overcount vs. the backend's
 * normalized `get_departments()` count. */
export function normalizeDesignationLabel(value: string): string {
  const titleCased = value
    .trim()
    .split(' ')
    .map((word) => (word ? word[0].toUpperCase() + word.slice(1).toLowerCase() : word))
    .join(' ')
  return titleCased.replace(/Tbd/g, 'TBD')
}

/** Count of distinct Designation values after normalization — use this
 * (not `distinctValues(..., 'designation').length`) for any Departments
 * KPI computed client-side, to stay consistent with the backend's
 * `get_departments()`. */
export function distinctDepartmentsCount(employees: EmployeeRecord[]): number {
  const set = new Set<string>()
  for (const e of employees) {
    const v = e.designation
    if (v !== null && v !== undefined && String(v).trim() !== '') {
      set.add(normalizeDesignationLabel(String(v)))
    }
  }
  return set.size
}

/** Count of distinct `Skill` values, mirroring the backend's confirmed
 * `get_skills_covered` DAX measure exactly: DISTINCTCOUNT of the (broader)
 * `Skill` column, excluding blank values and any value containing the
 * substring "TBD". Used to recompute the Skills & Experience page's
 * "Skills Covered" KPI client-side so it stays filter-reactive — the
 * unfiltered result must match `/roster/summary`'s `skills_covered` (16)
 * exactly as a sanity check. Do NOT use `distinctValues(..., 'skill')`
 * directly for this KPI since it doesn't apply the "TBD"-substring
 * exclusion the real DAX measure applies. */
export function distinctSkillsCoveredCount(employees: EmployeeRecord[]): number {
  const set = new Set<string>()
  for (const e of employees) {
    const v = e.skill
    if (v !== null && v !== undefined && String(v).trim() !== '' && !String(v).includes('TBD')) {
      set.add(String(v))
    }
  }
  return set.size
}

/** Mirrors `normalizeDesignationLabel`'s title-case approach, applied to
 * `Primary Skill` to collapse the "React JS" (2 rows) vs "React Js" (1
 * row) casing-duplicate data-quality issue found in that column (same
 * bug class as the already-fixed `Designation`/`Seniorirty Level`
 * duplicates). This page's skill-bifurcation charts are pivoted
 * client-side from the filtered employee list (not the backend's
 * `/roster/skills`, which does not normalize `Primary Skill`), so the
 * fix belongs here rather than in the backend. */
export function normalizePrimarySkillLabel(value: string): string {
  const titleCased = value
    .trim()
    .split(' ')
    .map((word) => (word ? word[0].toUpperCase() + word.slice(1).toLowerCase() : word))
    .join(' ')
  return titleCased.replace(/Tbd/g, 'TBD')
}

/** Distinct, sorted, non-empty values for a field across a list of
 * employees, after applying a normalizer to each raw value first — used
 * for filter dropdown option lists where the raw column has
 * casing-duplicate data-quality issues (e.g. Primary Skill's "React JS"
 * vs "React Js") so the dropdown shows one merged option instead of one
 * per raw casing variant. */
export function distinctNormalizedValues(
  employees: EmployeeRecord[],
  field: keyof EmployeeRecord,
  normalize: (value: string) => string,
): string[] {
  const set = new Set<string>()
  for (const e of employees) {
    const v = e[field]
    if (v !== null && v !== undefined && String(v).trim() !== '') {
      set.add(normalize(String(v)))
    }
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b))
}

/** Explicit ordinal order for `GRADE`, per the data-model skill: values
 * like `G3A`, `G4`...`G8` do NOT sort alphabetically (`G3A` < `G4`), and
 * `Grade TBD` (added 2026-07-15) must get an explicit slot rather than
 * sorting implicitly among the numbered grades. Unknown/unlisted values
 * sort after everything else but before `Grade TBD`. */
const GRADE_ORDER = ['G1', 'G2', 'G3', 'G3A', 'G4', 'G5', 'G6', 'G7', 'G8', 'G9', 'Grade TBD']

export function gradeSortRank(grade: string | null | undefined): number {
  if (!grade) return GRADE_ORDER.length - 1
  const idx = GRADE_ORDER.indexOf(grade)
  if (idx === -1) return GRADE_ORDER.length - 1
  return idx
}

/** Comparator for GRADE columns — use instead of default string sort,
 * which would incorrectly put `G3A` after `G4` alphabetically. */
export function compareGrade(a: string | null, b: string | null): number {
  return gradeSortRank(a) - gradeSortRank(b)
}

export function groupCount(values: string[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const v of values) out[v] = (out[v] ?? 0) + 1
  return out
}

/** Applies a set of { field: selectedValue } filters to an employee list.
 * A value of ALL (or unset) means "no filter on this field". `normalizers`
 * optionally maps a filter key to a normalizer function; when present, both
 * the selected value and the employee's raw field value are normalized
 * before comparing, so a merged dropdown option (e.g. Primary Skill's
 * "React Js") matches every raw casing variant instead of only an exact
 * string match. */
export function applyEmployeeFilters<T extends object>(
  employees: T[],
  filters: FilterValues,
  fieldMap: Record<string, keyof T>,
  normalizers: Record<string, (value: string) => string> = {},
): T[] {
  return employees.filter((e) =>
    Object.entries(filters).every(([key, val]) => {
      if (!val || val === ALL) return true
      const field = fieldMap[key]
      if (!field) return true
      const raw = String(e[field] ?? '')
      const normalize = normalizers[key]
      if (normalize) return normalize(raw) === normalize(val)
      return raw === val
    }),
  )
}
