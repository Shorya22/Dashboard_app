import { Info } from 'lucide-react'

/** Small visual flag for data-quality-flagged (PROVISIONAL) fields — the
 * backend's OpenAPI descriptions already flag these, this surfaces the same
 * warning to the end user instead of hiding it. */
export function ProvisionalBadge({ note }: { note?: string }) {
  return (
    <span
      className="group relative inline-flex cursor-help items-center text-amber-500"
      tabIndex={0}
    >
      <Info className="h-3.5 w-3.5" />
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-1.5 w-56 -translate-x-1/2 rounded-md border border-border bg-popover p-2 text-xs font-normal text-popover-foreground opacity-0 shadow-md transition-opacity group-hover:opacity-100 group-focus:opacity-100"
      >
        {note ??
          'Provisional — bucket boundaries are a best-effort guess, not yet confirmed against the real Power BI DAX. See the data-model skill.'}
      </span>
    </span>
  )
}
