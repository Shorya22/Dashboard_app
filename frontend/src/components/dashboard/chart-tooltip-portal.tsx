import * as React from 'react'
import { createPortal } from 'react-dom'

interface ChartTooltipPortalProps {
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
 * hovered element sits. */
export function ChartTooltipPortal({ active, containerRect, coordinate, children }: ChartTooltipPortalProps) {
  const nodeRef = React.useRef<HTMLDivElement>(null)
  const [pos, setPos] = React.useState<{ top: number; left: number } | null>(null)

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

  if (!active || anchorX == null || anchorY == null) return null

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
