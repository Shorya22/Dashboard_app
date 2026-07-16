// Shared long-label handling for chart category axes (Tremor BarChart's
// `index` field). Chosen approach across every chart with a category axis:
// truncate the axis tick to a fixed max length with an ellipsis, and show
// the untruncated label in the tooltip on hover (dashboard-design bug-fix
// pass, option A) — applied consistently, never mixed with wrapping/margin
// approaches.

const MAX_LABEL_LENGTH = 16

export function truncateLabel(label: string, maxLength: number = MAX_LABEL_LENGTH): string {
  if (label.length <= maxLength) return label
  return `${label.slice(0, Math.max(1, maxLength - 1)).trimEnd()}…`
}

/** Field name used to stash the untruncated label alongside the (now
 * truncated) index value, so a custom tooltip can display it in full. */
export const FULL_LABEL_KEY = '__fullLabel'

/** Returns a copy of `rows` with the `indexKey` field truncated for axis
 * display, plus the original value preserved under FULL_LABEL_KEY. */
export function withTruncatedLabels<T extends object>(
  rows: T[],
  indexKey: keyof T,
  maxLength: number = MAX_LABEL_LENGTH,
): Array<T & Record<string, unknown>> {
  return rows.map((row) => {
    const original = String(row[indexKey] as unknown)
    return {
      ...row,
      [indexKey]: truncateLabel(original, maxLength),
      [FULL_LABEL_KEY]: original,
    } as T & Record<string, unknown>
  })
}

/** Formats a chart value (bar/line/tooltip) for display. The underlying
 * hours data is only ever meaningful to one decimal place, but summing it
 * client-side produces binary floating-point noise (e.g. `1334.2999999999997`
 * instead of `1334.3`) — rounding to one decimal before formatting collapses
 * that noise back to the real value instead of just truncating the display
 * string. Also adds comma thousands separators, matching the KPI cards'
 * number formatting elsewhere in the app. Non-finite/non-numeric input is
 * passed through unchanged (e.g. a category name reused as a tooltip value). */
export function formatChartValue(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return String(value ?? '')
  const rounded = Math.round(value * 10) / 10
  return rounded.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 1 })
}
