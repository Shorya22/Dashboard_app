import * as React from 'react'
import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'

interface EntitySearchPickerProps {
  options: string[]
  onSelect: (value: string) => void
  placeholder?: string
  isLoading?: boolean
  isError?: boolean
}

/**
 * Full-width searchable list used by the Employee/Project Utilization
 * "picker" landing pages (no name pre-selected via URL param). Typing
 * filters the option list client-side; clicking a row navigates onward.
 * Not a dropdown/combobox — the full list stays visible inline since this
 * is the entire content of the page, matching the picker's role as a
 * standalone landing state rather than a form field.
 */
export function EntitySearchPicker({
  options,
  onSelect,
  placeholder = 'Search…',
  isLoading = false,
  isError = false,
}: EntitySearchPickerProps) {
  const [query, setQuery] = React.useState('')

  const filtered = React.useMemo(() => {
    if (!query.trim()) return options
    const q = query.toLowerCase()
    return options.filter((o) => o.toLowerCase().includes(q))
  }, [options, query])

  return (
    <div className="mx-auto w-full max-w-xl space-y-4">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className="h-11 pl-9"
        />
      </div>

      <div className="max-h-[420px] overflow-y-auto rounded-2xl border border-border bg-card shadow-card">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-9 animate-pulse rounded-lg bg-muted/50" />
            ))}
          </div>
        ) : isError ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            Couldn't load options. Try refreshing.
          </p>
        ) : filtered.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            {options.length === 0 ? 'No options available.' : `No matches for "${query}".`}
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {filtered.map((opt) => (
              <li key={opt}>
                <button
                  type="button"
                  onClick={() => onSelect(opt)}
                  className="w-full px-4 py-2.5 text-left text-sm text-foreground transition-colors hover:bg-muted/50"
                >
                  {opt}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
