import * as React from 'react'
import { Card, Text, Metric } from '@tremor/react'
import { ArrowUpRight, ArrowDownRight, type LucideIcon } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { ProvisionalBadge } from './provisional-badge'
import { useCountUp } from '@/lib/use-count-up'

/** Splits a KPI value like `"12.3%"` or `1234` into its numeric part (for
 * animating) and a fixed prefix/suffix (for re-assembling the display
 * string). Values with no parseable number (e.g. `'—'`) animate is skipped. */
function parseAnimatable(value: string | number): { numeric: number; decimals: number; prefix: string; suffix: string } | null {
  const str = String(value)
  const match = str.match(/^(\D*)(-?\d+(?:\.\d+)?)(\D*)$/)
  if (!match) return null
  const [, prefix, numStr, suffix] = match
  const decimals = numStr.includes('.') ? numStr.split('.')[1].length : 0
  return { numeric: parseFloat(numStr), decimals, prefix, suffix }
}

/** Displays a KPI metric that counts up from 0 to its value on mount and on
 * every subsequent data refresh, rather than snapping straight to the number. */
function AnimatedMetric({ value }: { value: string | number }) {
  const parsed = React.useMemo(() => parseAnimatable(value), [value])
  const animated = useCountUp(parsed?.numeric ?? null)

  if (!parsed || animated === null) {
    return <Metric className="text-2xl font-semibold tracking-tight">{value}</Metric>
  }

  const display = `${parsed.prefix}${animated.toFixed(parsed.decimals)}${parsed.suffix}`
  return <Metric className="text-2xl font-semibold tracking-tight tabular-nums">{display}</Metric>
}

interface KpiCardProps {
  label: string
  value: string | number
  delta?: { value: number; positiveIsGood?: boolean }
  loading?: boolean
  provisional?: boolean
  provisionalNote?: string
  icon?: LucideIcon
  iconTone?: 'blue' | 'orange' | 'emerald' | 'red'
}

const TONE_CLASSES: Record<NonNullable<KpiCardProps['iconTone']>, string> = {
  blue: 'bg-primary/10 text-primary',
  orange: 'bg-accent-orange/10 text-accent-orange',
  emerald: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  red: 'bg-destructive/10 text-destructive',
}

export function KpiCard({
  label,
  value,
  delta,
  loading,
  provisional,
  provisionalNote,
  icon: Icon,
  iconTone = 'blue',
}: KpiCardProps) {
  if (loading) {
    return (
      <Card className="rounded-2xl border-border bg-card p-5 shadow-card">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-xl" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-24" />
            <Skeleton className="h-7 w-16" />
          </div>
        </div>
      </Card>
    )
  }

  const isPositive = delta ? delta.value >= 0 : undefined
  const isGood = delta ? (delta.positiveIsGood ?? true) === isPositive : undefined

  return (
    <Card className="rounded-2xl border-border bg-card p-5 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-1.5">
            <Text className="text-muted-foreground">{label}</Text>
            {provisional && <ProvisionalBadge note={provisionalNote} />}
          </div>
          {delta !== undefined && (
            <p
              className={cn(
                'mt-1 text-xs font-medium uppercase tracking-[0.12em]',
                isGood ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive',
              )}
            >
              {isPositive ? 'Improving' : 'Declining'}
            </p>
          )}
        </div>
        {Icon && (
          <span className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-xl', TONE_CLASSES[iconTone])}>
            <Icon className="h-5 w-5" />
          </span>
        )}
      </div>
      <div className="mt-4 flex items-end justify-between gap-4">
        <AnimatedMetric value={value} />
        {delta !== undefined && (
          <span
            className={cn(
              'flex items-center gap-1 rounded-full border px-3 py-1 text-sm font-semibold',
              isGood
                ? 'border-emerald-100 bg-emerald-50 text-emerald-700 dark:border-emerald-300/30 dark:bg-emerald-500/10 dark:text-emerald-200'
                : 'border-destructive/20 bg-destructive/10 text-destructive dark:border-destructive/30 dark:bg-destructive/15',
            )}
          >
            {isPositive ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
            {Math.abs(delta.value).toFixed(1)}%
          </span>
        )}
      </div>
    </Card>
  )
}
