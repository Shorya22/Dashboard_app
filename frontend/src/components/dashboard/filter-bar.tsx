import { ALL, type FilterDef, type FilterValues } from '@/lib/employee-filters'
import {
  HierarchicalMultiSelect,
  type HierarchicalItem,
} from '@/components/dashboard/hierarchical-multi-select'

/** A hierarchical, multi-select filter (e.g. Region > Market) rendered in the
 * same row as the plain dropdowns. Uses the same tree component as the Search
 * page, so nested filters look and behave identically everywhere. */
export interface HierarchicalFilterDef {
  key: string
  label: string
  items: HierarchicalItem[]
  selected: string[]
  onChange: (values: string[]) => void
  searchable?: boolean
}

interface FilterBarProps {
  filters: FilterDef[]
  values: FilterValues
  onChange: (key: string, value: string) => void
  /** Nested multi-select filters (rendered before the plain dropdowns). */
  hierarchical?: HierarchicalFilterDef[]
}

/** Reusable filter row: a native-select dropdown per plain filter definition
 * (each with an "All" default), plus any hierarchical multi-select filters
 * (Region/Market and the like). All controls write into filter state owned by
 * the parent page, which every KPI/chart on the page reads from — never local
 * per-chart state — per the dashboard-design skill's filter-propagation rule. */
export function FilterBar({ filters, values, onChange, hierarchical }: FilterBarProps) {
  return (
    <div className="flex flex-col flex-wrap items-stretch gap-3 rounded-2xl border border-border bg-card p-3 shadow-card sm:flex-row sm:items-center">
      {hierarchical?.map((h) => (
        <div
          key={h.key}
          className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-none sm:flex-row sm:items-center sm:gap-2"
        >
          <label className="text-xs font-medium text-muted-foreground">{h.label}</label>
          <div className="w-full min-w-0 sm:w-[200px]">
            <HierarchicalMultiSelect
              items={h.items}
              selected={h.selected}
              onChange={h.onChange}
              searchable={h.searchable}
              placeholder="All"
            />
          </div>
        </div>
      ))}
      {filters.map((f) => (
        <div key={f.key} className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-none sm:flex-row sm:items-center sm:gap-2">
          <label htmlFor={`filter-${f.key}`} className="text-xs font-medium text-muted-foreground">
            {f.label}
          </label>
          <select
            id={`filter-${f.key}`}
            value={values[f.key] ?? ALL}
            onChange={(e) => onChange(f.key, e.target.value)}
            className="w-full min-w-0 max-w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm sm:w-auto sm:max-w-[220px]"
          >
            {f.options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      ))}
    </div>
  )
}
