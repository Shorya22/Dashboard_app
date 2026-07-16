import * as React from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Filter, ChevronLeft, ChevronRight } from 'lucide-react'

import { cn } from '@/lib/utils'

interface FiltersPanelProps {
  children: React.ReactNode
  defaultOpen?: boolean
}

/**
 * Collapsible right-edge "Filters" strip used on the utilization Results /
 * Employee / Project drill-through pages, matching the Power BI
 * reference's narrow vertical panel. Filter controls passed as `children`
 * are unchanged functionally — this only relocates them visually into a
 * docked, toggleable panel instead of an inline row.
 */
export function FiltersPanel({ children, defaultOpen = false }: FiltersPanelProps) {
  const [open, setOpen] = React.useState(defaultOpen)

  return (
    <div className="flex shrink-0 items-start">
      {/* Mobile/tablet (<lg): off-canvas overlay drawer from the right, with
          backdrop, so it never squeezes the main content column. */}
      <AnimatePresence initial={false}>
        {open && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              className="absolute inset-0 bg-black/50"
              onClick={() => setOpen(false)}
            />
            <motion.div
              key="mobile-panel"
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className="absolute inset-y-0 right-0 flex w-[85vw] max-w-[320px] flex-col gap-3 overflow-y-auto border-l border-border bg-card p-4 shadow-card"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <Filter className="h-4 w-4" />
                  Filters
                </div>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Close filters"
                  className="rounded-md p-1 text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
              <div className="flex flex-col gap-3">{children}</div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Desktop (lg+): inline docked panel that pushes/shares space with
          the main content column, as before. */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="panel"
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 260, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="hidden overflow-hidden lg:block"
          >
            <div className="flex w-[260px] flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-card">
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <Filter className="h-4 w-4" />
                Filters
              </div>
              <div className="flex flex-col gap-3">{children}</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Collapse filters' : 'Expand filters'}
        aria-expanded={open}
        className={cn(
          'ml-2 flex w-9 flex-col items-center gap-2 self-stretch rounded-2xl border border-border bg-card py-3 text-muted-foreground shadow-card transition-colors hover:bg-muted/50 hover:text-foreground',
        )}
      >
        {open ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        <Filter className="h-4 w-4" />
        <span
          className="mt-1 text-[11px] font-semibold uppercase tracking-wider"
          style={{ writingMode: 'vertical-rl' }}
        >
          Filters
        </span>
      </button>
    </div>
  )
}
