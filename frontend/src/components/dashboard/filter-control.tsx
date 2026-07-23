import * as React from 'react'
import { cn } from '@/lib/utils'

/**
 * Canonical Tailwind class string for every filter trigger across the
 * dashboard. Used by `FilterSelect` (shadcn Select), the native `<select>`
 * inside `FilterBar`, and `HierarchicalMultiSelect`'s popover trigger so all
 * three read as one system per the dashboard-design skill.
 */
// `min-w-0` lets the trigger shrink inside its fixed-width parent
// (`FilterControl`'s `sm:w-[180px]`) so long selected values can be
// truncated by the inner `<span className="truncate">` — without it the
// trigger keeps its intrinsic content width and spills past the border
// (a real bug: `BE Salesforce Commerce cloud Developer` overflowing the
// Department dropdown). `overflow-hidden` is a belt-and-braces so any
// child that forgot `truncate` still can't paint outside the border.
export const filterTriggerClasses =
  'flex h-10 w-full min-w-0 items-center justify-between gap-2 overflow-hidden rounded-md border border-border bg-background px-3 text-sm text-foreground transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50'

interface FilterControlProps {
  label: string
  htmlFor?: string
  className?: string
  children: React.ReactNode
}

/**
 * Label + trigger wrapper used by every filter control on the dashboard.
 * Provides the fixed label styling and width behavior (fluid on mobile,
 * fixed 180px on desktop) so every filter row looks identical.
 */
export function FilterControl({ label, htmlFor, className, children }: FilterControlProps) {
  return (
    <div
      className={cn(
        'flex min-w-0 flex-1 flex-col gap-1 sm:flex-none sm:w-[180px]',
        className,
      )}
    >
      <label
        htmlFor={htmlFor}
        className="mb-1 text-left text-xs font-medium text-muted-foreground"
      >
        {label}
      </label>
      {children}
    </div>
  )
}
