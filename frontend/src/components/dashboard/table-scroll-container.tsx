import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface TableScrollContainerProps {
  children: ReactNode
  className?: string
}

/** Wraps a wide table in a horizontally-scrollable container and shows a
 * right-edge fade/shadow cue whenever there's more content off-screen —
 * the cue disappears once scrolled to the end. Without this, a table that
 * is technically `overflow-x-auto` gives mobile users no visual signal
 * that swiping right reveals more columns. Used by every full-width data
 * table page per the dashboard-design skill's table rules. */
export function TableScrollContainer({ children, className }: TableScrollContainerProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [canScrollRight, setCanScrollRight] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const update = () => {
      setCanScrollRight(el.scrollWidth - el.clientWidth - el.scrollLeft > 4)
    }

    update()
    el.addEventListener('scroll', update, { passive: true })
    const resizeObserver = new ResizeObserver(update)
    resizeObserver.observe(el)

    return () => {
      el.removeEventListener('scroll', update)
      resizeObserver.disconnect()
    }
  }, [children])

  return (
    <div className="relative">
      <div
        ref={ref}
        className={cn(
          'overflow-x-auto rounded-2xl border border-border bg-card shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover',
          className,
        )}
      >
        {children}
      </div>
      <div
        aria-hidden="true"
        className={cn(
          'pointer-events-none absolute inset-y-0 right-0 w-10 rounded-r-2xl bg-gradient-to-l from-card via-card/70 to-transparent transition-opacity duration-200',
          canScrollRight ? 'opacity-100' : 'opacity-0',
        )}
      />
    </div>
  )
}
