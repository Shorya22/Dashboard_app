import { ChevronDown } from 'lucide-react'
import { ALL, type FilterDef, type FilterValues } from '@/lib/employee-filters'
import {
  HierarchicalMultiSelect,
  type HierarchicalItem,
} from '@/components/dashboard/hierarchical-multi-select'
import { FilterControl, filterTriggerClasses } from '@/components/dashboard/filter-control'
import { cn } from '@/lib/utils'

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
    <div className="flex flex-col flex-wrap items-stretch gap-3 rounded-2xl border border-border bg-card p-3 shadow-card sm:flex-row sm:items-end">
      {hierarchical?.map((h) => (
        <FilterControl key={h.key} label={h.label}>
          <HierarchicalMultiSelect
            items={h.items}
            selected={h.selected}
            onChange={h.onChange}
            searchable={h.searchable}
            placeholder="All"
          />
        </FilterControl>
      ))}
      {filters.map((f) => (
        <FilterControl key={f.key} label={f.label} htmlFor={`filter-${f.key}`}>
          <div className="relative w-full">
            <select
              id={`filter-${f.key}`}
              value={values[f.key] ?? ALL}
              onChange={(e) => onChange(f.key, e.target.value)}
              className={cn(filterTriggerClasses, 'appearance-none pr-8')}
            >
              {f.options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 opacity-50" />
          </div>
        </FilterControl>
      ))}
    </div>
  )
}
