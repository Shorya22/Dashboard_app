import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { FilterControl, filterTriggerClasses } from './filter-control'

interface FilterSelectProps {
  label: string
  value: string | undefined
  options: string[]
  onChange: (value: string | undefined) => void
  placeholder?: string
  /** Optional display-label override per raw option value (e.g. Market
   * (EC)'s BN -> BENO / Technology -> AMER alias). The underlying `value`
   * submitted via `onChange` is always the raw option string. */
  getOptionLabel?: (rawValue: string) => string
}

const ALL = '__all__'

/** A single labeled filter dropdown. `value` undefined = "All". Used across
 * utilization pages so every filter looks and behaves the same way. */
export function FilterSelect({
  label,
  value,
  options,
  onChange,
  placeholder,
  getOptionLabel,
}: FilterSelectProps) {
  return (
    <FilterControl label={label}>
      <Select
        value={value ?? ALL}
        onValueChange={(v) => onChange(v === ALL ? undefined : v)}
      >
        <SelectTrigger className={filterTriggerClasses}>
          {/* Wrap in a truncating span so long selected values (e.g. the
              roster-derived Department option "BE Salesforce Commerce
              cloud Developer") ellipsize inside the fixed 180px trigger
              instead of overflowing the border. `min-w-0 flex-1` lets
              the span shrink; `truncate` applies overflow-ellipsis. */}
          <span className="min-w-0 flex-1 truncate text-left">
            <SelectValue placeholder={placeholder ?? `All ${label}`} />
          </span>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All {label}</SelectItem>
          {options.map((opt) => (
            <SelectItem key={opt} value={opt}>
              {getOptionLabel ? getOptionLabel(opt) : opt}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </FilterControl>
  )
}
