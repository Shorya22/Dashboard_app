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
  height = 'h-72',
  children,
}: ChartCardProps) {
  return (
    <Card className="rounded-2xl border-border bg-card p-2 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover">
      <div className="flex items-center gap-1.5">
        <Title className="text-sm font-semibold text-foreground">{title}</Title>
      </div>
      {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      {/* Tremor pins bar/line chart tooltips to a fixed y=0 (top of the plot
          area) rather than following the cursor vertically, so it can sit
          very close to the title above. `pt-1` gives it just enough
          breathing room to avoid touching the subtitle, without eating
          into the declared chart `height` the way a larger value would. */}
      <div className={`relative mt-2 overflow-visible pt-1 ${height}`}>
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
