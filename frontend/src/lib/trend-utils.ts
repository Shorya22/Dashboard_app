export function computePercentDelta(
  current: number | undefined | null,
  previous: number | undefined | null,
): number | undefined {
  if (current == null || previous == null || previous === 0) return undefined
  return Number((((current - previous) / previous) * 100).toFixed(1))
}

export function latestDelta<T>(
  items: T[],
  valueFn: (item: T) => number | undefined | null,
): number | undefined {
  if (items.length < 2) return undefined
  const current = valueFn(items.at(-1)!)
  const previous = valueFn(items.at(-2)!)
  return computePercentDelta(current, previous)
}
