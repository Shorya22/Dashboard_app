import * as React from 'react'
import {
  LineChart as RLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LabelList,
  ResponsiveContainer,
} from 'recharts'
import { PRIMARY_COLOR, tremorHex } from '@/lib/chart-colors'
import { truncateLabel, formatChartValue } from '@/lib/chart-labels'
import { createFullLabelTooltip } from './full-label-tooltip'
import { CustomLegend } from './custom-legend'

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
 * font sizes, grid, axis, and tooltip via `createFullLabelTooltip`), used instead
 * of Tremor's own component because Tremor's public API has no data-label
 * passthrough — the Power BI reference always shows the value permanently
 * above every point, not just on hover. The legend is the same `CustomLegend`
 * used by the bar and donut charts (swatch + name, rendered as plain HTML
 * below the plot rather than Recharts' own in-SVG `<Legend>`) so all three
 * chart types share one consistent legend look instead of each having its
 * own slightly different styling. */
export function CustomLineChart({
  data,
  index,
  category,
  color = PRIMARY_COLOR,
  yAxisLabel,
  xAxisLabel,
  className,
}: CustomLineChartProps) {
  const stroke = tremorHex(color)

  // See custom-bar-chart.tsx: the tooltip portal needs this chart
  // instance's own wrapper rect to translate Recharts' in-chart cursor
  // coordinate into a viewport position.
  const containerRef = React.useRef<HTMLDivElement>(null)
  const tooltipContent = React.useMemo(
    () => createFullLabelTooltip({ getContainerRect: () => containerRef.current?.getBoundingClientRect() ?? null }),
    [],
  )

  // Permanent per-point value labels (below) match the Power BI reference
  // for a handful of points, but with many data points along the x-axis
  // the labels sit close enough together to overlap each other — there's
  // no collision avoidance in Recharts' LabelList. Past this threshold,
  // rely on the tooltip (still shows every value on hover) instead of
  // forcing all of them to render permanently.
  const showPointLabels = data.length <= 12

  // Extra bottom room whenever an axis title stacks below the tick labels,
  // so the two don't collide. The legend used to need to be accounted for
  // here too, back when it was Recharts' own in-SVG `<Legend>` — now that
  // it's the plain-HTML `CustomLegend` rendered below the chart instead,
  // this only needs room for the tick labels + axis title themselves.
  const bottomMargin = xAxisLabel ? 30 : 4

  return (
    <div ref={containerRef} className="flex h-full w-full flex-col">
      <ResponsiveContainer width="100%" height="100%" className={className}>
        <RLineChart data={data} margin={{ top: 20, right: 10, left: 4, bottom: bottomMargin }}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-tremor-border dark:text-dark-tremor-border" vertical={false} />
          <XAxis
            dataKey={index}
            tick={{ fontSize: 12, fontWeight: 500 }}
            tickFormatter={(value: string) => truncateLabel(value)}
            className="fill-tremor-content dark:fill-dark-tremor-content"
            axisLine={{ className: 'stroke-tremor-border dark:stroke-dark-tremor-border' } as never}
            tickLine={false}
            tickMargin={6}
            label={xAxisLabel ? { value: xAxisLabel, position: 'bottom', offset: 2, fontSize: 13, fontWeight: 500 } : undefined}
          />
          <YAxis
            // Headroom past the highest point so its permanent value label
            // (rendered just above the dot) never gets clipped against the
            // axis max / card edge — same fix as the bar chart's domain.
            domain={[0, (max: number) => Math.ceil(max * 1.15)]}
            tick={{ fontSize: 12, fontWeight: 500 }}
            className="fill-tremor-content dark:fill-dark-tremor-content"
            axisLine={false}
            tickLine={false}
            tickMargin={4}
            label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft', fontSize: 13, fontWeight: 500 } : undefined}
          />
          <Tooltip content={tooltipContent as unknown as any} cursor={{ strokeDasharray: '3 3' }} />
          <Line
            type="linear"
            dataKey={category}
            stroke={stroke}
            strokeWidth={2.25}
            dot={{ r: 3, fill: stroke, strokeWidth: 0 }}
            activeDot={{ r: 6, strokeWidth: 2, stroke: 'hsl(var(--card))' }}
            isAnimationActive
            animationDuration={1000}
          >
            {showPointLabels && (
              <LabelList
                dataKey={category}
                position="top"
                offset={10}
                formatter={formatChartValue as never}
                className="fill-tremor-content-strong dark:fill-dark-tremor-content-strong"
                // A permanent label sitting at the same height as one of the
                // dashed gridlines gets the dashes bleeding through its
                // strokes, reading as struck-through text. A stroked halo
                // painted behind the fill (paintOrder: 'stroke') masks
                // whatever's behind the glyphs regardless of where they land.
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  paintOrder: 'stroke',
                  stroke: 'hsl(var(--card))',
                  strokeWidth: 4,
                  strokeLinejoin: 'round',
                }}
              />
            )}
          </Line>
        </RLineChart>
      </ResponsiveContainer>
      <CustomLegend
        data={[{ name: category, value: 0 }]}
        colors={[color]}
        showValues={false}
        layout="wrap"
        className="mt-1.5 shrink-0 justify-center"
      />
    </div>
  )
}
