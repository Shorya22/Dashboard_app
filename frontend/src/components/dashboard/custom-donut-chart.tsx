import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, type PieLabelRenderProps } from 'recharts'
import { tremorHex } from '@/lib/chart-colors'
import { cn } from '@/lib/utils'
import { FullLabelTooltip } from './full-label-tooltip'

interface DonutDatum {
  name: string
  value: number
}

interface CustomDonutChartProps {
  data: DonutDatum[]
  colors: string[]
  className?: string
  /** Label shown under the bold center total, e.g. "Total" or a metric
   * name. Defaults to "Total". Pass `null` to omit the center overlay
   * entirely (rare — every donut should show a total per the design pass
   * on 2026-07-16 unless there's a specific reason not to). */
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

/** Recharts-based donut chart matching the Power BI reference: an external
 * callout label per slice showing "value (percent%)", plus a bold center
 * total + label overlay styled to match what Tremor's own `<DonutChart>`
 * center total looks like (Tremor's built-in version can't suppress that
 * total, so this custom component reimplements it deliberately instead).
 * Styled to sit next to Tremor's own charts: same tooltip, same color
 * tokens. */
export function CustomDonutChart({ data, colors, className, totalLabel = 'Total' }: CustomDonutChartProps) {
  const total = data.reduce((sum, d) => sum + d.value, 0)

  const renderLabel = (props: PieLabelRenderProps) => {
    const { cx, cy, midAngle, outerRadius, value, index } = props
    const RADIAN = Math.PI / 180
    const radius = Number(outerRadius) + 22
    const angle = midAngle ?? 0
    const x = Number(cx) + radius * Math.cos(-angle * RADIAN)
    const y = Number(cy) + radius * Math.sin(-angle * RADIAN)
    const numericValue = typeof value === 'number' ? value : Number(value)
    const label = `${formatValue(numericValue)} (${formatPercent(numericValue, total)})`
    const color = colors[index ?? 0] ? tremorHex(colors[index ?? 0]) : undefined

    return (
      <text
        x={x}
        y={y}
        textAnchor={x > Number(cx) ? 'start' : 'end'}
        dominantBaseline="central"
        className="fill-tremor-content-strong text-[11px] font-semibold dark:fill-dark-tremor-content-strong"
        fill={color}
      >
        {label}
      </text>
    )
  }

  return (
    <div className={cn('relative h-full w-full', className)}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius="55%"
            outerRadius="70%"
            paddingAngle={3}
            isAnimationActive
            animationDuration={1000}
            label={renderLabel}
            labelLine={false}
          >
            {data.map((d, i) => (
              <Cell key={d.name} fill={tremorHex(colors[i] ?? 'slate')} stroke="transparent" />
            ))}
          </Pie>
          <Tooltip content={<FullLabelTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      {totalLabel !== null && (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-2xl font-semibold tracking-tight text-tremor-content-strong dark:text-dark-tremor-content-strong">
            {formatValue(total)}
          </span>
          <span className="mt-1 text-xs uppercase tracking-[0.24em] text-tremor-content dark:text-dark-tremor-content">
            {totalLabel}
          </span>
        </div>
      )}
    </div>
  )
}
