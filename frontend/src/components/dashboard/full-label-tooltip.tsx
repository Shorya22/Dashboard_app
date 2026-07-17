import type { CustomTooltipProps } from '@tremor/react'
import { FULL_LABEL_KEY, formatChartValue } from '@/lib/chart-labels'
import { ChartTooltipPortal } from './chart-tooltip-portal'

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

interface CreateFullLabelTooltipOptions {
  /** Real metric name for a single-series chart's generic `value` dataKey
   * (see `displayName` above). Omit for multi-series charts, where
   * `item.name` is already a real category name (e.g. a region or
   * seniority band). */
  valueLabel?: string
  /** Returns the chart's own wrapper rect (viewport coordinates), captured
   * by the caller via a ref on the element that directly wraps
   * `<ResponsiveContainer>` — Recharts' `coordinate` is relative to that
   * box. Every chart must supply this: it's what lets `ChartTooltipPortal`
   * translate an in-chart cursor position into a real viewport position for
   * its `document.body` portal, and without it the tooltip can't render at
   * all (no anchor to position from). */
  getContainerRect: () => DOMRect | null
}

/** Builds a tooltip content component for a Recharts `<Tooltip content={...}>`
 * that shows the *untruncated* category label (stashed by
 * `withTruncatedLabels` under FULL_LABEL_KEY) instead of the
 * ellipsis-truncated axis tick text, plus a meaningful series label instead
 * of the raw "value" dataKey — and renders via `ChartTooltipPortal` so it
 * always sits clear of the hovered bar/point instead of overlapping it. Used
 * by every Recharts chart (bar, line) so the tooltip visual language —
 * rounded corners, subtle border/shadow, colored series dot, muted label +
 * bold value, fade-in — is identical everywhere. Each chart instance must
 * create its own bound copy (typically via `useMemo`) with a
 * `getContainerRect` closed over that chart's own wrapper ref — the returned
 * component isn't reusable across chart instances since it needs a
 * different container each time. */
export function createFullLabelTooltip(options: CreateFullLabelTooltipOptions) {
  const { valueLabel, getContainerRect } = options

  function BoundFullLabelTooltip({ active, payload, label, coordinate }: CustomTooltipProps) {
    if (!active || !payload || payload.length === 0) return null

    const fullLabel = (payload[0]?.payload?.[FULL_LABEL_KEY] as string | undefined) ?? label
    const items = payload.filter((item) => item.type !== 'none')
    const containerRect = getContainerRect()

    return (
      <ChartTooltipPortal active={active} containerRect={containerRect} coordinate={coordinate}>
        <div className="max-w-[260px] animate-in fade-in-0 zoom-in-95 duration-150 rounded-xl border border-tremor-border bg-tremor-background shadow-lg dark:border-dark-tremor-border dark:bg-dark-tremor-background">
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
      </ChartTooltipPortal>
    )
  }
  return BoundFullLabelTooltip
}
