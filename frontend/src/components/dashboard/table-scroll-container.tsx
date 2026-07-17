import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface TableScrollContainerProps {
  children: ReactNode
  className?: string
  /** Caps the table's own height so it scrolls internally instead of the
   * whole page — see the component doc comment for why this also happens
   * to be what makes `<thead className="sticky top-0">` actually stick.
   * Any valid CSS height value (`'70vh'`, `'480px'`, ...). Set `null` to
   * opt out for a table that's always short enough not to need it. */
  maxHeight?: string | null
}

/** Wraps a wide table in a horizontally-scrollable container and shows a
 * right-edge fade/shadow cue whenever there's more content off-screen —
 * the cue disappears once scrolled to the end. Without this, a table that
 * is technically `overflow-x-auto` gives mobile users no visual signal
 * that swiping right reveals more columns. Used by every full-width data
 * table page per the dashboard-design skill's table rules.
 *
 * Also bounds the table's height with its own `overflow-y-auto` (default
 * 70vh) rather than letting it grow to the page's full scroll length. This
 * isn't just nicer UX (pagination controls below the table stay in view
 * instead of requiring a scroll past however many rows the table has) — a
 * bounded `overflow-y` here is *required* for every page's `<thead
 * className="sticky top-0">` to actually stick. Per the CSS overflow spec,
 * setting only `overflow-x: auto` still forces the browser to compute
 * `overflow-y` as `auto` too (the two axes can't have one `auto` and the
 * other `visible`) — so without an explicit height, this container was
 * *already* a vertical scroll container, just one whose height always
 * matched its content exactly, giving `position: sticky` nothing to stick
 * against. Bounding the height on purpose is what makes the sticky header
 * a real, working feature instead of a class name doing nothing. */
export function TableScrollContainer({ children, className, maxHeight = '70vh' }: TableScrollContainerProps) {
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
        style={maxHeight ? { maxHeight } : undefined}
        className={cn(
          'overflow-x-auto rounded-2xl border border-border bg-card shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover',
          maxHeight && 'overflow-y-auto',
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
