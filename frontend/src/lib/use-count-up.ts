import * as React from 'react'

/** Eases a numeric display value from 0 up to `target` over `duration` ms,
 * driven by requestAnimationFrame. Re-runs whenever `target` changes (e.g.
 * on data refresh) so KPI cards always animate into their new value rather
 * than snapping. Non-numeric targets are returned unchanged, un-animated. */
export function useCountUp(target: number | null, duration = 700): number | null {
  const [value, setValue] = React.useState<number | null>(target)
  const fromRef = React.useRef(0)
  const rafRef = React.useRef<number>()

  React.useEffect(() => {
    if (target === null) {
      setValue(null)
      return
    }
    const from = fromRef.current
    const delta = target - from
    if (delta === 0) {
      setValue(target)
      return
    }
    const start = performance.now()

    const tick = (now: number) => {
      const elapsed = now - start
      const t = Math.min(1, elapsed / duration)
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3)
      const current = from + delta * eased
      setValue(current)
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick)
      } else {
        fromRef.current = target
      }
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, duration])

  return value
}
