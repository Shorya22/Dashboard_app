import {
  LineChart as RLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  LabelList,
  ResponsiveContainer,
} from 'recharts'
import { tremorHex } from '@/lib/chart-colors'
import { FullLabelTooltip } from './full-label-tooltip'

interface CustomLineChartProps {
  data: Record<string, string | number>[]
  index: string
  category: string
  color?: string
  yAxisLabel?: string
  xAxisLabel?: string
  className?: string
}

/** Recharts-based line chart, styled to match Tremor's `<LineChart>` (same
 * font sizes, grid, axis, and tooltip via `FullLabelTooltip`), used instead
 * of Tremor's own component because Tremor's public API has no data-label
 * passthrough — the Power BI reference always shows the value permanently
 * above every point, not just on hover. */
export function CustomLineChart({
  data,
  index,
  category,
  color = 'orange',
  yAxisLabel,
  xAxisLabel,
  className,
}: CustomLineChartProps) {
  const stroke = tremorHex(color)

  return (
    <ResponsiveContainer width="100%" height="100%" className={className}>
      <RLineChart data={data} margin={{ top: 24, right: 16, left: 8, bottom: xAxisLabel ? 24 : 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-tremor-border dark:text-dark-tremor-border" vertical={false} />
        <XAxis
          dataKey={index}
          tick={{ fontSize: 12 }}
          className="fill-tremor-content dark:fill-dark-tremor-content"
          axisLine={{ className: 'stroke-tremor-border dark:stroke-dark-tremor-border' } as never}
          tickLine={false}
          label={xAxisLabel ? { value: xAxisLabel, position: 'insideBottom', offset: -10, fontSize: 13 } : undefined}
        />
        <YAxis
          tick={{ fontSize: 12 }}
          className="fill-tremor-content dark:fill-dark-tremor-content"
          axisLine={false}
          tickLine={false}
          label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft', fontSize: 13 } : undefined}
        />
        <Tooltip content={<FullLabelTooltip />} />
        <Legend wrapperStyle={{ fontSize: 13 }} />
        <Line
          type="linear"
          dataKey={category}
          stroke={stroke}
          strokeWidth={2}
          dot={{ r: 3, fill: stroke, strokeWidth: 0 }}
          activeDot={{ r: 5 }}
          isAnimationActive
          animationDuration={1000}
        >
          <LabelList
            dataKey={category}
            position="top"
            offset={10}
            className="fill-tremor-content-strong dark:fill-dark-tremor-content-strong"
            style={{ fontSize: 12, fontWeight: 600 }}
          />
        </Line>
      </RLineChart>
    </ResponsiveContainer>
  )
}
