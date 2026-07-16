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
export function withTruncatedLabels<T extends Record<string, unknown>>(
  rows: T[],
  indexKey: keyof T,
  maxLength: number = MAX_LABEL_LENGTH,
): T[] {
  return rows.map((row) => {
    const original = String(row[indexKey])
    return {
      ...row,
      [indexKey]: truncateLabel(original, maxLength),
      [FULL_LABEL_KEY]: original,
    }
  })
}
