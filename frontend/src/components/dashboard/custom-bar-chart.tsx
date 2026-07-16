import {
  BarChart as RBarChart,
  Bar,
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

interface BarSeries {
  category: string
  color: string
}

interface CustomBarChartProps {
  data: Record<string, string | number>[]
  index: string
  /** Single-series mode: bar dataKey. Ignored if `series` is passed. */
  category?: string
  color?: string
  /** Multi-series (grouped) mode: pass 2+ series to render side-by-side
   * bars per category, each with its own permanent value labels — e.g.
   * Joiners vs Exits. */
  series?: BarSeries[]
  layout?: 'horizontal' | 'vertical'
  yAxisLabel?: string
  xAxisLabel?: string
  yAxisWidth?: number
  showLegend?: boolean
  className?: string
}

/** Recharts-based bar chart, styled to match Tremor's `<BarChart>` (same
 * font sizes, grid, axis, and tooltip via `FullLabelTooltip`), used instead
 * of Tremor's own component because Tremor's public `<BarChart>` API has no
 * data-label passthrough — the Power BI reference always shows the value
 * permanently on/above every bar, not just on hover. Supports either a
 * single `category` or a `series` array for grouped/multi-series bars
 * (e.g. Joiners vs Exits), both with permanent labels. */
export function CustomBarChart({
  data,
  index,
  category,
  color = 'orange',
  series,
  layout = 'horizontal',
  yAxisLabel,
  xAxisLabel,
  yAxisWidth = 40,
  showLegend,
  className,
}: CustomBarChartProps) {
  const fill = tremorHex(color)
  const isVertical = layout === 'vertical'
  const bars: BarSeries[] = series ?? (category ? [{ category, color }] : [])

  return (
    <ResponsiveContainer width="100%" height="100%" className={className}>
      <RBarChart
        data={data}
        layout={isVertical ? 'vertical' : 'horizontal'}
        margin={{
          top: 24,
          right: isVertical ? 32 : 16,
          left: 8,
          bottom: !isVertical && xAxisLabel ? 24 : 8,
        }}
      >
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="currentColor"
          className="text-tremor-border dark:text-dark-tremor-border"
          horizontal={!isVertical}
          vertical={isVertical}
        />
        {isVertical ? (
          <>
            <XAxis
              type="number"
              tick={{ fontSize: 12 }}
              className="fill-tremor-content dark:fill-dark-tremor-content"
              axisLine={false}
              tickLine={false}
              label={xAxisLabel ? { value: xAxisLabel, position: 'insideBottom', offset: -10, fontSize: 13 } : undefined}
            />
            <YAxis
              type="category"
              dataKey={index}
              tick={{ fontSize: 12 }}
              className="fill-tremor-content dark:fill-dark-tremor-content"
              axisLine={{ className: 'stroke-tremor-border dark:stroke-dark-tremor-border' } as never}
              tickLine={false}
              width={yAxisWidth}
              label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft', fontSize: 13 } : undefined}
            />
          </>
        ) : (
          <>
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
              width={yAxisWidth}
              label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft', fontSize: 13 } : undefined}
            />
          </>
        )}
        <Tooltip content={<FullLabelTooltip />} cursor={{ fill: 'currentColor', className: 'text-tremor-background-subtle dark:text-dark-tremor-background-subtle', opacity: 0.5 }} />
        {showLegend && <Legend wrapperStyle={{ fontSize: 13 }} />}
        {bars.map((bar) => (
          <Bar
            key={bar.category}
            name={bar.category}
            dataKey={bar.category}
            fill={tremorHex(bar.color)}
            isAnimationActive
            animationDuration={1000}
            radius={isVertical ? [0, 4, 4, 0] : [4, 4, 0, 0]}
          >
            <LabelList
              dataKey={bar.category}
              position={isVertical ? 'right' : 'top'}
              offset={8}
              className="fill-tremor-content-strong dark:fill-dark-tremor-content-strong"
              style={{ fontSize: 12, fontWeight: 600 }}
            />
          </Bar>
        ))}
      </RBarChart>
    </ResponsiveContainer>
  )
}
