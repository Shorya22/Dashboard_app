import { tremorHex } from '@/lib/chart-colors'
import { cn } from '@/lib/utils'

export interface LegendDatum {
  name: string
  value: number
}

interface CustomLegendProps {
  data: LegendDatum[]
  colors: string[]
  /** Value formatter — defaults to a plain string cast. Pass the same
   * formatter used elsewhere on the chart (e.g. donut's K-abbreviation) so
   * the legend's numbers match what's shown on hover/in the center total. */
  formatValue?: (value: number) => string
  /** Total to compute each row's percentage share against. Omit to hide
   * the percentage column (e.g. when the values aren't parts of one whole). */
  total?: number
  className?: string
  /** 'list' stacks rows vertically (default, used below/beside a chart).
   * 'wrap' lets rows flow and wrap horizontally — useful when legend sits
   * in a tight horizontal strip. */
  layout?: 'list' | 'wrap'
  /** Show each row's value + percentage. Default true. Set false to keep
   * the legend to just a swatch + name — e.g. when the chart itself
   * already carries the numbers (slice labels, tooltip on hover) and a
   * second copy in the legend is redundant clutter rather than useful. */
  showValues?: boolean
}

function defaultFormat(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

/** Shared legend for donut/pie charts: colored swatch + category name
 * (truncated with a `title` tooltip for overflow) + value + percentage of
 * total. Replaces ad hoc inline legend markup so every chart's legend looks
 * and behaves identically. */
export function CustomLegend({
  data,
  colors,
  formatValue = defaultFormat,
  total,
  className,
  layout = 'list',
  showValues = true,
}: CustomLegendProps) {
  if (data.length === 0) return null
  const computedTotal = total ?? data.reduce((sum, d) => sum + d.value, 0)

  return (
    <div
      className={cn(
        layout === 'wrap' ? 'flex flex-wrap gap-x-4 gap-y-2' : 'grid gap-2',
        className,
      )}
    >
      {data.map((d, index) => {
        const pct = computedTotal === 0 ? 0 : (d.value / computedTotal) * 100
        return (
          <div
            key={d.name}
            className={cn(
              'flex min-w-0 items-center gap-2 text-sm',
              layout === 'list' && showValues && 'justify-between',
            )}
          >
            <div className="flex min-w-0 items-center gap-2">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: tremorHex(colors[index] ?? 'slate') }}
              />
              <span
                className="truncate text-tremor-content dark:text-dark-tremor-content"
                title={d.name}
              >
                {d.name}
              </span>
            </div>
            {showValues && (
              <span className="shrink-0 whitespace-nowrap font-semibold text-tremor-content-strong dark:text-dark-tremor-content-strong">
                {formatValue(d.value)}
                {computedTotal > 0 && (
                  <span className="ml-1 font-normal text-tremor-content dark:text-dark-tremor-content">
                    · {pct.toFixed(1)}%
                  </span>
                )}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
