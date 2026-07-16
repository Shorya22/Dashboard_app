import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

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
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      <Select
        value={value ?? ALL}
        onValueChange={(v) => onChange(v === ALL ? undefined : v)}
      >
        <SelectTrigger className="w-[180px]">
          <SelectValue placeholder={placeholder ?? `All ${label}`} />
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
    </div>
  )
}
