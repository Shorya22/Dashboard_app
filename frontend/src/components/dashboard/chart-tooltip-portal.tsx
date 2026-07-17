import * as React from 'react'
import { createPortal } from 'react-dom'
import { claimActiveTooltip, releaseActiveTooltip, useIsActiveTooltip } from '@/lib/chart-tooltip-touch-store'

interface ChartTooltipPortalProps {
  /** The chart instance's own stable id (`React.useId()`, generated once
   * for the chart's whole lifetime by its parent — see
   * custom-bar-chart.tsx / custom-line-chart.tsx), not a fresh id per
   * hover. See chart-tooltip-touch-store.ts for why that stability is
   * what actually fixes the "tooltip sometimes just doesn't show" bug. */
  ownerId: string
  active?: boolean
  /** The chart's own wrapper element rect (viewport/client coordinates),
   * captured by the caller via a ref. Recharts' `coordinate` is relative to
   * this box, so translating through it is what lets the tooltip escape
   * every ancestor's `overflow: hidden` (the page shell's scroll container,
   * a card, the chart's own SVG) — the portal renders straight into
   * `document.body` as `position: fixed`, so no ancestor clipping applies
   * to it at all. */
  containerRect: DOMRect | null
  /** Recharts' cursor position, relative to `containerRect`. */
  coordinate?: { x?: number; y?: number }
  children: React.ReactNode
}

const GAP = 12
const VIEWPORT_MARGIN = 8

/** Renders chart tooltip content into a `document.body` portal, positioned
 * with real collision detection against the viewport instead of Recharts'
 * own in-chart absolute positioning (which happily overlaps bars/labels and
 * gets clipped by any ancestor's `overflow: hidden`). Measures its own
 * rendered size, then picks above/below and left/right placement based on
 * which side actually has room — flipping and clamping as needed so the
 * tooltip can never overlap the hovered point, clip, or overflow the
 * viewport, regardless of chart type, zoom level, or where in the card the
 * hovered element sits.
 *
 * Claiming is keyed off *when `active` becomes true*, not off this
 * component's own mount/unmount — Recharts may or may not fully unmount
 * its tooltip content between two hovered points on the same chart
 * depending on version/interaction path, and the earlier version of this
 * fix tied ownership to that unmount timing, which raced: a chart could
 * lose and immediately re-claim its own slot on every point, and
 * depending on exactly when React flushed each effect, a claim could land
 * in the wrong order relative to a dismiss and the tooltip just wouldn't
 * show — "sometimes it works, sometimes it doesn't." Combined with
 * `ownerId` being a *stable per-chart* id (not fresh per activation), one
 * claim now covers a whole continuous hover/touch session regardless of
 * how Recharts renders it internally. `isOwner` is the actual visibility
 * gate — a scroll, a touch-drag, a tap elsewhere, or another chart's
 * tooltip claiming the slot all clear it here even while Recharts' own
 * `active` still says true, since touch has no `mouseleave` to do that
 * for us. */
export function ChartTooltipPortal({ ownerId, active, containerRect, coordinate, children }: ChartTooltipPortalProps) {
  const nodeRef = React.useRef<HTMLDivElement>(null)
  const [pos, setPos] = React.useState<{ top: number; left: number } | null>(null)

  React.useEffect(() => {
    if (!active) return
    claimActiveTooltip(ownerId)
    return () => releaseActiveTooltip(ownerId)
  }, [active, ownerId])

  const isOwner = useIsActiveTooltip(ownerId)

  const anchorX = containerRect && coordinate?.x != null ? containerRect.left + coordinate.x : null
  const anchorY = containerRect && coordinate?.y != null ? containerRect.top + coordinate.y : null

  React.useLayoutEffect(() => {
    if (!active || anchorX == null || anchorY == null) {
      setPos(null)
      return
    }
    const node = nodeRef.current
    if (!node) return
    const { width, height } = node.getBoundingClientRect()
    const vw = window.innerWidth
    const vh = window.innerHeight

    // Vertical: prefer sitting above the hovered point (keeps it clear of
    // the bar/line below); flip below only when there's provably more room
    // there than above.
    const spaceAbove = anchorY - GAP - VIEWPORT_MARGIN
    const spaceBelow = vh - anchorY - GAP - VIEWPORT_MARGIN
    let top = spaceAbove >= height || spaceAbove >= spaceBelow ? anchorY - GAP - height : anchorY + GAP

    // Horizontal: center on the cursor, then clamp off the viewport edges.
    let left = anchorX - width / 2
    if (left + width > vw - VIEWPORT_MARGIN) left = vw - VIEWPORT_MARGIN - width
    if (left < VIEWPORT_MARGIN) left = VIEWPORT_MARGIN

    // Final clamp — guarantees full visibility even for a tooltip taller or
    // wider than the available space (dense payloads, narrow viewports).
    top = Math.min(Math.max(top, VIEWPORT_MARGIN), Math.max(VIEWPORT_MARGIN, vh - VIEWPORT_MARGIN - height))
    left = Math.min(Math.max(left, VIEWPORT_MARGIN), Math.max(VIEWPORT_MARGIN, vw - VIEWPORT_MARGIN - width))

    setPos({ top, left })
    // Re-measure on every anchor move (each hovered point/bar) — the
    // content (series count, label length) can change size between them.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, anchorX, anchorY])

  // `isOwner` is the override: a scroll, a touch-drag, a tap elsewhere, or
  // another chart's tooltip claiming the slot all clear it here even while
  // Recharts' own `active` still says true (see the component doc comment
  // above for why touch specifically needs this).
  if (!active || anchorX == null || anchorY == null || !isOwner) return null

  return createPortal(
    <div
      ref={nodeRef}
      style={{
        position: 'fixed',
        top: pos?.top ?? 0,
        left: pos?.left ?? 0,
        zIndex: 9999,
        pointerEvents: 'none',
        visibility: pos ? 'visible' : 'hidden',
      }}
    >
      {children}
    </div>,
    document.body,
  )
}
