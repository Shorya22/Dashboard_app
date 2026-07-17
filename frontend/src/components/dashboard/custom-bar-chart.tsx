import * as React from 'react'
import {
  BarChart as RBarChart,
  Bar,
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

interface BarSeries {
  category: string
  color: string
}

interface CustomBarChartProps {
  // Accept a more flexible data shape — many callers provide typed rows
  // augmented with extra keys. Widening to `Record<string, unknown>`
  // avoids index-signature errors while preserving caller typing.
  data: Record<string, unknown>[]
  index: string
  /** Single-series mode: bar dataKey. Ignored if `series` is passed. */
  category?: string
  color?: string
  tooltipValueLabel?: string
  /** Multi-series (grouped) mode: pass 2+ series to render side-by-side
   * bars per category, each with its own permanent value labels — e.g.
   * Joiners vs Exits. */
  series?: BarSeries[]
  stack?: boolean
  layout?: 'horizontal' | 'vertical'
  yAxisLabel?: string
  xAxisLabel?: string
  yAxisWidth?: number
  showLegend?: boolean
  className?: string
}

/** Recharts-based bar chart, styled to match Tremor's `<BarChart>` (same
 * font sizes, grid, axis, and tooltip via `createFullLabelTooltip`), used instead
 * of Tremor's own component because Tremor's public `<BarChart>` API has no
 * data-label passthrough — the Power BI reference always shows the value
 * permanently on/above every bar, not just on hover. Supports either a
 * single `category` or a `series` array for grouped/multi-series bars
 * (e.g. Joiners vs Exits), both with permanent labels. The legend (when
 * shown) is the same `CustomLegend` used by the line and donut charts —
 * plain HTML below the plot, not Recharts' own in-SVG `<Legend>` — so all
 * three chart types share one consistent legend look. */
export function CustomBarChart({
  data,
  index,
  category,
  color = PRIMARY_COLOR,
  tooltipValueLabel,
  series,
  stack = false,
  layout = 'horizontal',
  yAxisLabel,
  xAxisLabel,
  yAxisWidth = 40,
  showLegend,
  className,
}: CustomBarChartProps) {
  const isVertical = layout === 'vertical'
  const bars: BarSeries[] = series ?? (category ? [{ category, color }] : [])

  // The tooltip portal needs this chart instance's own wrapper rect to
  // translate Recharts' in-chart cursor coordinate into a viewport
  // position — see chart-tooltip-portal.tsx. Rebuilt only when the value
  // label changes, not on every render.
  const containerRef = React.useRef<HTMLDivElement>(null)
  const tooltipContent = React.useMemo(
    () =>
      createFullLabelTooltip({
        valueLabel: tooltipValueLabel,
        getContainerRect: () => containerRef.current?.getBoundingClientRect() ?? null,
      }),
    [tooltipValueLabel],
  )

  const stackId = stack ? 'stack' : undefined

  // Permanent value labels read as "value on every bar" only while there's
  // room for them. Past this many bars (categories × series, since grouped
  // series each get their own label), labels sit too close together and
  // start overlapping their neighbors — Recharts' LabelList has no
  // collision avoidance. Beyond the threshold, drop the permanent labels
  // and rely on the tooltip (still shows every value on hover), same
  // fallback pattern as the line chart's `showPointLabels`.
  const totalBarCount = data.length * Math.max(bars.length, 1)
  const showBarLabels = totalBarCount <= 24

  // Safety-net truncation for the category axis: callers are expected to
  // pre-truncate long labels via `withTruncatedLabels` (chart-labels.ts),
  // but when they don't, a long raw label rendered at a fixed axis width
  // (especially the vertical layout's narrow `yAxisWidth`, default 40px)
  // overflows into the plot area and collides with bars/gridlines. This
  // formatter re-truncates defensively so that never happens, regardless
  // of what the caller passed in. In vertical layout the available width
  // is `yAxisWidth`, so the char budget scales with it instead of using
  // the wider default (~16 chars) meant for a full-width x-axis.
  const categoryTickFormatter = isVertical
    ? (value: string) => truncateLabel(value, Math.max(4, Math.floor(yAxisWidth / 6)))
    : (value: string) => truncateLabel(value)

  return (
    <div ref={containerRef} className="flex h-full w-full flex-col">
      <ResponsiveContainer width="100%" height="100%" className={className}>
        <RBarChart
          data={data}
          layout={isVertical ? 'vertical' : 'horizontal'}
          margin={{
            top: 16,
            right: isVertical ? 24 : 10,
            left: 4,
            // Extra bottom room when an x-axis title is present: the
            // legend (when shown) now renders as plain HTML below the
            // chart, not inside this SVG margin, so this only needs to
            // clear the tick labels + axis title themselves.
            bottom: xAxisLabel ? 28 : 4,
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
                // Headroom past the longest bar so its permanent value
                // label (rendered just past the bar's end) never touches
                // or gets clipped by the axis's own max tick/edge — without
                // this, a bar that happens to reach exactly the auto-scaled
                // axis max has nowhere for its label to sit.
                domain={[0, (max: number) => Math.ceil(max * 1.15)]}
                tick={{ fontSize: 12, fontWeight: 500 }}
                className="fill-tremor-content dark:fill-dark-tremor-content"
                axisLine={false}
                tickLine={false}
                label={xAxisLabel ? { value: xAxisLabel, position: 'bottom', offset: 2, fontSize: 13 } : undefined}
              />
              <YAxis
                type="category"
                dataKey={index}
                tick={{ fontSize: 12, fontWeight: 500 }}
                tickFormatter={categoryTickFormatter}
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
                tick={{ fontSize: 12, fontWeight: 500 }}
                tickFormatter={categoryTickFormatter}
                className="fill-tremor-content dark:fill-dark-tremor-content"
                axisLine={{ className: 'stroke-tremor-border dark:stroke-dark-tremor-border' } as never}
                tickLine={false}
                label={xAxisLabel ? { value: xAxisLabel, position: 'bottom', offset: 2, fontSize: 13 } : undefined}
              />
              <YAxis
                // Same headroom fix as the vertical layout's XAxis above —
                // room for the tallest bar's permanent value label so it
                // doesn't get clipped against the axis max / card edge.
                domain={[0, (max: number) => Math.ceil(max * 1.15)]}
                tick={{ fontSize: 12, fontWeight: 500 }}
                className="fill-tremor-content dark:fill-dark-tremor-content"
                axisLine={false}
                tickLine={false}
                width={yAxisWidth}
                label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft', fontSize: 13 } : undefined}
              />
            </>
          )}
          <Tooltip
            content={tooltipContent as unknown as any}
            // No cursor rectangle: Recharts' default bar cursor is a
            // translucent fill spanning the *entire* category's height —
            // for grouped series it covers every bar (and their permanent
            // LabelList values) at that category, not just the hovered one.
            // Sitting on top of the labels' stroked halo, it read as
            // doubled/ghosted text (a gray wash over already-rendered
            // digits) rather than a hover affordance. Each `<Bar>` below
            // gets its own `activeBar` highlight instead, confined to the
            // one bar actually under the cursor.
            cursor={false}
          />
          {bars.map((bar) => (
            <Bar
              key={bar.category}
              name={bar.category}
              dataKey={bar.category}
              fill={tremorHex(bar.color)}
              stackId={stackId}
              isAnimationActive
              animationDuration={1000}
              radius={isVertical ? [0, 4, 4, 0] : [4, 4, 0, 0]}
              // Without a cap, Recharts stretches bars to fill whatever
              // space is available — fine with a dozen categories, but a
              // chart with only 3-4 bars spread across a full-width card
              // ends up with each bar ~150-200px thick. Capping thickness
              // keeps every bar chart's bar width visually consistent
              // regardless of category count or card width; the leftover
              // space just becomes gap between bars instead.
              maxBarSize={48}
              // Hover feedback confined to the one bar under the cursor
              // (replaces the old chart-wide cursor rectangle).
              activeBar={{ fillOpacity: 0.85 }}
            >
              {showBarLabels && (
                <LabelList
                  dataKey={bar.category}
                  position={isVertical ? 'right' : 'top'}
                  offset={8}
                  formatter={formatChartValue as never}
                  className="fill-tremor-content-strong dark:fill-dark-tremor-content-strong"
                  // See custom-line-chart.tsx: a stroked halo keeps the value
                  // legible when it lands on a dashed gridline instead of
                  // reading as struck-through.
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
            </Bar>
          ))}
        </RBarChart>
      </ResponsiveContainer>
      {showLegend && bars.length > 0 && (
        <CustomLegend
          data={bars.map((b) => ({ name: b.category, value: 0 }))}
          colors={bars.map((b) => b.color)}
          showValues={false}
          layout="wrap"
          className="mt-1.5 shrink-0 justify-center"
        />
      )}
    </div>
  )
}
