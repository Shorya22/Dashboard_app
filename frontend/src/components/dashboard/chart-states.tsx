import { Card, Title } from '@tremor/react'
import { AlertTriangle, Inbox } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { ProvisionalBadge } from './provisional-badge'

interface ChartCardProps {
  title: string
  subtitle?: string
  isLoading: boolean
  isError: boolean
  isEmpty?: boolean
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
  provisional,
  provisionalNote,
  height = 'h-72',
  children,
}: ChartCardProps) {
  return (
    <Card className="rounded-2xl border-border bg-card p-5 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover">
      <div className="flex items-center gap-1.5">
        <Title className="text-sm font-semibold text-foreground">{title}</Title>
        {provisional && <ProvisionalBadge note={provisionalNote} />}
      </div>
      {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      {/* Tremor pins bar/line chart tooltips to a fixed y=0 (top of the plot
          area) rather than following the cursor vertically, so it can sit
          very close to the title above. `pt-3` gives it breathing room
          without changing the declared chart `height`. */}
      <div className={`relative mt-4 overflow-visible pt-3 ${height}`}>
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
