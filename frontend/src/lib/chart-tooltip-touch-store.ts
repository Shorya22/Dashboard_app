import * as React from 'react'

// Coordinates every chart's tooltip/hover-detail state (bar + line tooltips
// via ChartTooltipPortal, and the donut's own in-place center-detail swap)
// so touch interaction behaves like a real mobile app instead of Recharts'
// raw default. The problems this fixes are all the same root cause:
// Recharts tracks each chart's own active/hover state internally and
// independently, driven only by that one chart's own mouse/touch events —
// there is no built-in concept of "the user started scrolling, dismiss" or
// "another chart just activated, close mine" or "the user tapped elsewhere
// on the page." Touch makes this concrete and visible: there's no touch
// equivalent of `mouseleave`, so once a tap activates something, Recharts'
// own internal state stays "active" indefinitely.
//
// This is a plain module-level store (not React context) for the same
// reason as chart-theme-store.ts: the global dismiss listeners below need
// to reach every mounted chart synchronously, from outside React's render
// cycle, which only a shared external store makes simple.

const AUTO_DISMISS_MS = 4000
// Only touch-activated tooltips get an inactivity auto-dismiss — a desktop
// user legitimately hovering one point for a while shouldn't have the
// tooltip vanish out from under a cursor that never left.
const isCoarsePointer = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches === true

// Owner ids are each chart's own *stable* id (`React.useId()`, generated
// once for the chart's whole lifetime — see custom-bar-chart.tsx /
// custom-line-chart.tsx), not a fresh id per hover/tap. Claiming keys off
// of *when `active` becomes true*, not off of mount/unmount — Recharts may
// or may not fully unmount its tooltip content between two hovered points
// on the same chart depending on version/interaction path, and tying
// ownership to that unmount timing was the bug: a chart could lose and
// immediately re-claim its own slot on every point, and depending on
// exactly when React flushed each effect, a claim could occasionally land
// in the wrong order relative to a dismiss and the tooltip just wouldn't
// show — reported as "sometimes it works, sometimes it doesn't." Keying
// off the `active` value itself instead of component lifecycle removes
// that race entirely: one claim per continuous hover/touch session,
// full stop.
let activeOwnerId: string | null = null
let dismissTimer: ReturnType<typeof setTimeout> | null = null
const listeners = new Set<() => void>()

// A separate counter, bumped only by an actual *global* dismiss (scroll,
// touch-drag, tap outside every chart) — not by every claim. Charts that
// don't render a floating tooltip at all (the donut, which swaps its own
// center label in place instead) subscribe to this directly via
// `useDismissSignal` rather than participating in the owner-slot system,
// since there's nothing for them to "own" — just a "clear your local
// hover state now" signal.
let dismissSignal = 0
const dismissListeners = new Set<() => void>()

function notify() {
  listeners.forEach((listener) => listener())
}

function notifyDismiss() {
  dismissSignal += 1
  dismissListeners.forEach((listener) => listener())
}

function clearDismissTimer() {
  if (dismissTimer) {
    clearTimeout(dismissTimer)
    dismissTimer = null
  }
}

/** Claims the single "currently visible tooltip" slot for `ownerId`,
 * evicting whatever tooltip held it before (the eviction is what makes
 * "only one tooltip at a time" true across independently-tracked charts).
 * Safe to call repeatedly with the same id — idempotent past the first
 * call bar resetting the auto-dismiss timer, which is the desired
 * behavior (still-active counts as still-recent). */
export function claimActiveTooltip(ownerId: string) {
  clearDismissTimer()
  activeOwnerId = ownerId
  if (isCoarsePointer()) {
    dismissTimer = setTimeout(() => {
      activeOwnerId = null
      notify()
    }, AUTO_DISMISS_MS)
  }
  notify()
}

/** Releases the slot — only if `ownerId` still holds it, so a release from
 * a chart that already lost the slot to a newer claim can't clobber that
 * newer claim. */
export function releaseActiveTooltip(ownerId: string) {
  if (activeOwnerId === ownerId) {
    activeOwnerId = null
    clearDismissTimer()
    notify()
  }
}

/** Forcibly clears the slot regardless of who holds it, and bumps the
 * dismiss signal every non-charting component (the donut) listens for —
 * the global scroll/touchmove/tap-outside listeners below are the only
 * callers. */
export function dismissActiveTooltip() {
  notifyDismiss()
  if (activeOwnerId === null) return
  activeOwnerId = null
  clearDismissTimer()
  notify()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Whether `ownerId` currently owns the visible slot. A chart's own
 * Recharts `active` prop can still say true after losing the slot — touch
 * has no `mouseleave` to clear that internal state — so this is the real
 * gate a tooltip renders behind, not just `active` alone. */
export function useIsActiveTooltip(ownerId: string): boolean {
  return React.useSyncExternalStore(
    subscribe,
    () => activeOwnerId === ownerId,
    () => activeOwnerId === ownerId,
  )
}

function subscribeDismiss(listener: () => void) {
  dismissListeners.add(listener)
  return () => dismissListeners.delete(listener)
}

/** A counter that increments on every *global* dismiss (scroll, touch-drag,
 * tap outside every chart). For charts with no floating tooltip to gate —
 * currently just the donut, which swaps its own center label on hover
 * instead — this is what to `useEffect`-watch to clear local hover state
 * (e.g. `activeIndex`) on the same triggers the bar/line tooltips dismiss
 * on, instead of it getting stuck after a tap with no corresponding
 * `mouseleave`. */
export function useDismissSignal(): number {
  return React.useSyncExternalStore(subscribeDismiss, () => dismissSignal, () => dismissSignal)
}

let globalListenersInstalled = false

// A real human tap is never perfectly stationary — a few pixels of
// incidental finger movement is normal and shouldn't read as "the user is
// now scrolling." Dismissing on *any* touchmove with zero threshold was
// the actual bug behind "tooltip shows sometimes, not others": whichever
// taps happened to have slightly more jitter than others fired a dismiss
// microseconds after Recharts activated the tooltip, so it would flash
// and vanish — indistinguishable, at a glance, from "never showed."
// Requiring real movement past a small threshold before treating it as a
// drag/scroll gesture is the standard fix for telling a tap from a swipe.
const TOUCH_MOVE_DISMISS_THRESHOLD_PX = 10
let touchStartX = 0
let touchStartY = 0

/** Installs the app-wide "what dismisses a tooltip" listeners exactly
 * once per page load. Idempotent — safe to call from more than one
 * component. */
export function installGlobalTooltipDismissal() {
  if (globalListenersInstalled || typeof document === 'undefined') return
  globalListenersInstalled = true

  // The `scroll` event doesn't bubble, so a plain listener on `document`
  // would only ever see the window/document scrolling — not the app's
  // actual scrollable main content area, or any scrollable card. Capture
  // phase is the fix: it travels top-down through every ancestor on the
  // way to the event's target regardless of whether that event type
  // normally bubbles back up, so one listener here sees scrolling
  // anywhere in the app.
  document.addEventListener('scroll', dismissActiveTooltip, { capture: true, passive: true })

  document.addEventListener(
    'touchstart',
    (event) => {
      const touch = event.touches[0]
      if (!touch) return
      touchStartX = touch.clientX
      touchStartY = touch.clientY
    },
    { passive: true },
  )

  // A touch drag starting is the mobile signal that the user is scrolling
  // the page, not reading the tooltip — dismiss as soon as the gesture
  // clears the jitter threshold, rather than waiting for the `scroll`
  // event, which can lag a frame behind the gesture actually starting.
  document.addEventListener(
    'touchmove',
    (event) => {
      const touch = event.touches[0]
      if (!touch) return
      const dx = touch.clientX - touchStartX
      const dy = touch.clientY - touchStartY
      if (dx * dx + dy * dy > TOUCH_MOVE_DISMISS_THRESHOLD_PX * TOUCH_MOVE_DISMISS_THRESHOLD_PX) {
        dismissActiveTooltip()
      }
    },
    { passive: true },
  )

  // Pointer Events unify mouse/touch/pen, so this one listener covers
  // "tap outside on mobile" and "click outside on desktop" alike. A
  // pointerdown *inside* another chart is deliberately left alone here —
  // that chart's own activation (claimActiveTooltip) is what evicts
  // whatever tooltip was open before, so two charts never end up visibly
  // open at once without this listener needing to know which is which.
  document.addEventListener(
    'pointerdown',
    (event) => {
      const target = event.target as Element | null
      if (target?.closest('.recharts-wrapper')) return
      dismissActiveTooltip()
    },
    { passive: true },
  )
}
