import { memo, useEffect, useState } from 'react'
import { PieChart, Pie, Cell, Sector, ResponsiveContainer, type SectorProps } from 'recharts'
import { tremorHex } from '@/lib/chart-colors'
import { useChartTheme } from '@/lib/chart-theme-store'
import { useDismissSignal } from '@/lib/chart-tooltip-touch-store'
import { cn } from '@/lib/utils'
import { CustomLegend } from './custom-legend'

interface DonutDatum {
  name: string
  value: number
}

interface CustomDonutChartProps {
  data: DonutDatum[]
  colors: string[]
  className?: string
  showLegend?: boolean
  /** Accessible label for the center total (e.g. "Total Hours") — read by
   * screen readers only. Earlier versions of this chart also showed this
   * as small print under the center number, but that reads as visual
   * clutter on a small donut and duplicates what the card's own title
   * already says, so it's sr-only now rather than removed outright. */
  totalLabel?: string | null
}

/** Formats a raw value the way the Power BI reference does: whole numbers
 * under 1000 as-is, otherwise abbreviated with a "K" suffix and up to 2
 * decimal places (e.g. 8928.6 -> "8.93K"). */
function formatValue(value: number): string {
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toFixed(2).replace(/\.?0+$/, '')}K`
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function formatPercent(value: number, total: number): string {
  if (total === 0) return '0%'
  return `${((value / total) * 100).toFixed(1)}%`
}

/** Renders the hovered slice a touch larger (outer radius nudged out) —
 * a subtle, non-bouncy hover affordance in line with the rest of the
 * dashboard's restrained motion, via Recharts' built-in active-shape hook
 * rather than a CSS transition (Recharts redraws the arc path on hover,
 * so CSS scale would distort from the wrong transform origin). */
function renderActiveShape(props: SectorProps) {
  const { outerRadius = 0, ...rest } = props
  return <Sector {...rest} outerRadius={Number(outerRadius) + 6} />
}

/** Recharts-based donut chart: a clean ring with no permanent on-chart
 * labels, and the legend below is swatch + name only. Name/value/percentage
 * for a slice show by swapping the *center* display on hover, instead of a
 * floating Recharts tooltip — a real tooltip near a small donut's own
 * center inevitably lands on top of the ring/center total it's supposed to
 * be detail for for, which reads as broken in a way no amount of tooltip
 * repositioning fixes. This is the same pattern Highcharts/ECharts use for
 * small donuts: hover a slice, the center swaps to that slice's detail;
 * un-hover, it swaps back to the aggregate total. No overlap is possible
 * because there's only ever one thing in that space at a time. Legend
 * below is swatch + name only (no numbers, no on-chart labels) — two
 * earlier approaches (external floating labels, then labels inside the
 * ring) both fought the same problem: any *permanent* on-chart label needs
 * guaranteed room a fluid, variously-sized-per-page donut can't always
 * provide, especially at the small end of a 3-column grid. Dropping
 * permanent labels entirely sidesteps that class of bug completely. */
export const CustomDonutChart = memo(function CustomDonutChart({
  data,
  colors,
  className,
  showLegend = true,
  totalLabel = 'Total',
}: CustomDonutChartProps) {
  // See custom-bar-chart.tsx — subscribes this chart to theme changes.
  useChartTheme()
  const [activeIndex, setActiveIndex] = useState<number | undefined>(undefined)
  const total = data.reduce((sum, d) => sum + d.value, 0)
  const activeDatum = activeIndex !== undefined ? data[activeIndex] : undefined

  // Touch has no `mouseleave`, so tapping a slice on mobile could leave
  // `activeIndex` stuck set indefinitely — the center display would keep
  // showing that slice's detail instead of reverting to the total. Reset
  // on the same signals the bar/line tooltips dismiss on (scroll,
  // touch-drag, tap outside every chart) — see chart-tooltip-touch-store.ts.
  const dismissSignal = useDismissSignal()
  useEffect(() => {
    setActiveIndex(undefined)
  }, [dismissSignal])

  return (
    <div className={cn('flex h-full w-full flex-col items-center gap-3', className)}>
      <div
        className="relative aspect-square h-full max-h-full min-h-0 flex-1"
        onMouseLeave={() => setActiveIndex(undefined)}
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius="58%"
              outerRadius="76%"
              paddingAngle={3}
              isAnimationActive
              animationDuration={1000}
              activeIndex={activeIndex}
              activeShape={renderActiveShape}
              onMouseEnter={(_, index) => setActiveIndex(index)}
              onMouseLeave={() => setActiveIndex(undefined)}
            >
              {data.map((d, i) => (
                <Cell key={d.name} fill={tremorHex(colors[i] ?? 'slate')} stroke="transparent" />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {totalLabel !== null && (
          // Constrained to the donut's inner hole (58% inner radius) so
          // text never spills out past the ring. `truncate` +
          // `whitespace-nowrap` keeps a large abbreviated total (e.g.
          // "12.34K") on one line instead of wrapping. Content swaps
          // between the aggregate total (idle) and the hovered slice's own
          // name + value + percent (active) — see the component doc
          // comment above for why this replaces a floating tooltip here.
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
            <div className="flex max-w-[58%] flex-col items-center">
              {activeDatum ? (
                <>
                  <span className="w-full truncate text-xs font-medium text-tremor-content dark:text-dark-tremor-content">
                    {activeDatum.name}
                  </span>
                  <span className="w-full truncate text-xl font-semibold tracking-tight text-tremor-content-strong dark:text-dark-tremor-content-strong">
                    {formatValue(activeDatum.value)}
                  </span>
                  <span className="w-full truncate text-xs text-tremor-content dark:text-dark-tremor-content">
                    {formatPercent(activeDatum.value, total)}
                  </span>
                </>
              ) : (
                <>
                  <span className="sr-only">{totalLabel}</span>
                  <span className="w-full truncate text-2xl font-semibold tracking-tight text-tremor-content-strong dark:text-dark-tremor-content-strong">
                    {formatValue(total)}
                  </span>
                </>
              )}
            </div>
          </div>
        )}
      </div>
      {showLegend && data.length > 0 && (
        <CustomLegend data={data} colors={colors} showValues={false} layout="wrap" className="shrink-0 justify-center" />
      )}
    </div>
  )
})
