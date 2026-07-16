import type { CustomTooltipProps } from '@tremor/react'
import { FULL_LABEL_KEY, formatChartValue } from '@/lib/chart-labels'

/** Tremor/Recharts gives every series item a `name` equal to its chart
 * `dataKey`. For single-series charts built from generic `{ name, value }`
 * rows (i.e. `categories={['value']}`), that dataKey is the literal string
 * "value" — meaningless in a tooltip. `valueLabel` supplies the real
 * metric name to show instead for that one series; every other series name
 * (multi-series / stacked charts) is left untouched. */
function displayName(itemName: string | undefined, valueLabel?: string): string {
  if (itemName === 'value' && valueLabel) return valueLabel
  return itemName ?? ''
}

/** Drop-in replacement for Tremor's default chart tooltip that shows the
 * *untruncated* category label (stashed by `withTruncatedLabels` under
 * FULL_LABEL_KEY) instead of the ellipsis-truncated axis tick text, plus a
 * meaningful series label instead of the raw "value" dataKey. Renders only
 * while `active` — i.e. only on hover, same as Tremor's own tooltip — so it
 * never stays stuck open once the mouse leaves the chart.
 *
 * Used for every chart on every page (bar, line, donut) so the tooltip
 * visual language — rounded corners, subtle border/shadow, colored series
 * dot, muted label + bold value, fade-in — is identical everywhere.
 *
 * Use directly for multi-series charts, where `item.name` is already a real
 * category name (e.g. a region or seniority band). For a single-series
 * chart built from `{ name, value }` rows, call
 * `createFullLabelTooltip('Employees')` (or whatever the metric is) and
 * pass the returned component instead — that's what turns the meaningless
 * "value" into a real label rather than just hiding it.
 */
/** Recharts' `<Pie>` computes a `percent` (0-1 fraction of the donut's
 * total) on each slice's payload internally — reuse it here rather than
 * recomputing, so a donut's tooltip shows "value (percent%)" matching the
 * chart's own external slice labels. Bar/line series payloads don't carry
 * this field, so it's simply omitted there (a "percent of what" question
 * that isn't always meaningful across grouped/stacked series). */
function percentOf(item: unknown): number | undefined {
  const raw = (item as { payload?: { percent?: number } })?.payload?.percent
  return typeof raw === 'number' ? raw : undefined
}

export function createFullLabelTooltip(valueLabel?: string) {
  function BoundFullLabelTooltip({ active, payload, label, coordinate, viewBox }: CustomTooltipProps) {
    if (!active || !payload || payload.length === 0) return null

    const fullLabel = (payload[0]?.payload?.[FULL_LABEL_KEY] as string | undefined) ?? label
    const items = payload.filter((item) => item.type !== 'none')

    // Recharts positions this tooltip relative to the cursor but doesn't
    // clamp it to the chart's own bounds, so near the right edge of a
    // narrow chart (or on mobile) it can overflow past the viewport/card
    // edge. Nudge the anchor so the tooltip flips to the left of the
    // cursor once there isn't enough room to the right, keeping it fully
    // inside the plot area.
    const plotWidth = typeof viewBox?.width === 'number' ? viewBox.width : undefined
    const cursorX = typeof coordinate?.x === 'number' ? coordinate.x : undefined
    const nearRightEdge = plotWidth !== undefined && cursorX !== undefined && cursorX > plotWidth - 140

    return (
      <div
        className={`max-w-[260px] animate-in fade-in-0 zoom-in-95 duration-150 rounded-xl border border-tremor-border bg-tremor-background shadow-lg dark:border-dark-tremor-border dark:bg-dark-tremor-background ${nearRightEdge ? '-translate-x-full' : ''}`}
      >
        <div className="border-b border-tremor-border px-3 py-2 dark:border-dark-tremor-border">
          <p className="break-words text-xs font-medium text-tremor-content-emphasis dark:text-dark-tremor-content-emphasis">
            {fullLabel}
          </p>
        </div>
        <div className="space-y-1.5 px-3 py-2">
          {items.map((item, i) => {
            const pct = percentOf(item)
            return (
              <div key={`${item.name}-${i}`} className="flex items-center gap-3">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
                <p className="flex-1 truncate text-xs text-tremor-content dark:text-dark-tremor-content">
                  {displayName(item.name as string | undefined, valueLabel)}
                </p>
                <p className="whitespace-nowrap font-semibold tabular-nums text-tremor-content-strong dark:text-dark-tremor-content-strong">
                  {formatChartValue(item.value)}
                  {pct !== undefined && (
                    <span className="ml-1 font-normal text-tremor-content dark:text-dark-tremor-content">
                      ({(pct * 100).toFixed(1)}%)
                    </span>
                  )}
                </p>
              </div>
            )
          })}
        </div>
      </div>
    )
  }
  return BoundFullLabelTooltip
}

/** Default tooltip for multi-series/stacked charts and for single-series
 * charts whose series already carries a real name (e.g. `['Closing
 * Headcount']`, `['Exits']`) — not the generic `['value']`. */
export const FullLabelTooltip = createFullLabelTooltip()
