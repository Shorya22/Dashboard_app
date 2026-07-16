import { ALL, type FilterDef, type FilterValues } from '@/lib/employee-filters'

interface FilterBarProps {
  filters: FilterDef[]
  values: FilterValues
  onChange: (key: string, value: string) => void
}

/** Reusable filter row: one native-select dropdown per filter definition,
 * each with an "All" default. Built directly with Tailwind (no shadcn
 * Select primitive exists in this codebase yet) per the dashboard-design
 * skill's fallback rule. All dropdowns write into one shared filter-state
 * object owned by the parent page, which every KPI/chart on the page reads
 * from — never local per-chart state — per the skill's filter-propagation
 * rule. */
export function FilterBar({ filters, values, onChange }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-border bg-card p-3 shadow-card">
      {filters.map((f) => (
        <div key={f.key} className="flex items-center gap-2">
          <label htmlFor={`filter-${f.key}`} className="text-xs font-medium text-muted-foreground">
            {f.label}
          </label>
          <select
            id={`filter-${f.key}`}
            value={values[f.key] ?? ALL}
            onChange={(e) => onChange(f.key, e.target.value)}
            className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
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
