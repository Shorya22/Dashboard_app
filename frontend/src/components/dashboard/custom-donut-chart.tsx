import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, type PieLabelRenderProps } from 'recharts'
import { tremorHex } from '@/lib/chart-colors'
import { FullLabelTooltip } from './full-label-tooltip'

interface DonutDatum {
  name: string
  value: number
}

interface CustomDonutChartProps {
  data: DonutDatum[]
  colors: string[]
  className?: string
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
 * callout label per slice showing "value (percent%)", and NO center total
 * (Tremor's `<DonutChart>` always renders a center total and has no prop to
 * suppress it, so this page uses a custom component instead). Styled to sit
 * next to Tremor's own charts: same tooltip, same color tokens. */
export function CustomDonutChart({ data, colors, className }: CustomDonutChartProps) {
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
    <ResponsiveContainer width="100%" height="100%" className={className}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius="55%"
          outerRadius="70%"
          paddingAngle={1}
          isAnimationActive
          animationDuration={1000}
          label={renderLabel}
          labelLine
        >
          {data.map((d, i) => (
            <Cell key={d.name} fill={tremorHex(colors[i] ?? 'gray')} stroke="transparent" />
          ))}
        </Pie>
        <Tooltip content={<FullLabelTooltip />} />
      </PieChart>
    </ResponsiveContainer>
  )
}
