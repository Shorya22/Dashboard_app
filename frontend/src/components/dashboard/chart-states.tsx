import { Card, Title } from '@tremor/react'
import { AlertTriangle, Inbox } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

interface ChartCardProps {
  title: string
  subtitle?: string
  isLoading: boolean
  isError: boolean
  isEmpty?: boolean
  // Still accepted (pages pass caveat text documenting data-quality/filter
  // notes for future reference) but intentionally not rendered — the
  // visual badge was removed per product feedback.
  provisional?: boolean
  provisionalNote?: string
  height?: string
  children: React.ReactNode
}

/** Wraps a Tremor chart with a consistent title, loading skeleton, and
 * error/empty state so no chart is ever left blank. */
export function ChartCard({
  title,
  subtitle,
  isLoading,
  isError,
  isEmpty,
  height = 'min-h-72',
  children,
}: ChartCardProps) {
  return (
    // `flex h-full flex-col`: when this card sits in a CSS grid row next to
    // a taller sibling (e.g. one with a subtitle that wraps to two lines),
    // the grid's default `align-items: stretch` makes the *card* taller to
    // match — but a plain block element doesn't pass that extra height down
    // to its children, so it used to show up as dead space below the chart,
    // inside the h-* box's own fixed height. Making the card a flex column
    // and the box below `flex-1` (see its own comment) means the chart
    // itself absorbs the growth instead — outside a grid, `h-full` resolves
    // to `auto` per spec (a percentage height against an auto-sizing
    // containing block computes to auto), so this doesn't collapse the card
    // to nothing when it's the only child in a normal-flow container.
    <Card className="flex h-full flex-col rounded-2xl border-border bg-card p-2 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover">
      <div className="flex items-center gap-1.5">
        <Title className="text-sm font-semibold text-foreground">{title}</Title>
      </div>
      {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      {/* Tremor pins bar/line chart tooltips to a fixed y=0 (top of the plot
          area) rather than following the cursor vertically, so it can sit
          very close to the title above. `pt-1` gives it just enough
          breathing room to avoid touching the subtitle, without eating
          into the declared chart `height` the way a larger value would.
          `height` is now a `min-h-*` floor (not a fixed `h-*`) — `flex-1`
          is what actually determines the rendered size, growing past that
          floor to fill whatever height the card ends up with. */}
      <div className={`relative mt-2 min-h-0 flex-1 overflow-visible pt-1 ${height}`}>
        {isLoading ? (
          <Skeleton className="h-full w-full rounded-xl" />
        ) : isError ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
            <AlertTriangle className="h-6 w-6" />
            <p className="text-sm">Couldn't load this chart. Try refreshing.</p>
          </div>
        ) : isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
            <Inbox className="h-6 w-6" />
            <p className="text-sm">No data for this view.</p>
          </div>
        ) : (
          children
        )}
      </div>
    </Card>
  )
}
