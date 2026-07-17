import * as React from 'react'

// Chart color themes — a small, curated set of pre-validated palettes
// (dataviz skill's `validate_palette.js`, run against this app's actual
// card surface #f8f8f9) rather than a free-form color picker. A picker
// would let a non-technical user land on a combination that fails
// color-blind separation or contrast without any way to know it; a preset
// list guarantees every option shipped here already passes those checks.
// All three keep the same brand blue as slot 1 (shared with the sidebar/
// buttons elsewhere in the app, not just charts) and only vary the 7
// companion hues, in the same fixed slot order (see chart-colors.ts).
export type ChartThemeName = 'soft' | 'vivid' | 'high-contrast'

interface ChartThemeDef {
  name: ChartThemeName
  label: string
  description: string
  hex: Record<string, string>
}

// Neutral/legacy tokens shared by every theme — "TBD"/"Other"/"Inactive"
// buckets intentionally stay a plain gray outside the categorical rotation
// regardless of theme, and the remaining tokens are kept only for any code
// not yet migrated onto the 8-slot set.
const SHARED_HEX = {
  slate: '#64748b',
  gray: '#6b7280',
  red: '#b8504f',
  sky: '#0ea5e9',
  cyan: '#06b6d4',
  orange: '#f97316',
  lime: '#84cc16',
  fuchsia: '#d946ef',
}

export const CHART_THEMES: Record<ChartThemeName, ChartThemeDef> = {
  soft: {
    name: 'soft',
    label: 'Soft',
    description: 'Light, muted, pastel-leaning tones. The default — calm and easy on the eyes for everyday use.',
    hex: {
      blue: '#1c4f97',
      teal: '#4fc4a7',
      violet: '#9e57c1',
      amber: '#c89b41',
      rose: '#c3557a',
      emerald: '#4abf5d',
      indigo: '#6057c1',
      terracotta: '#c86e41',
      ...SHARED_HEX,
    },
  },
  vivid: {
    name: 'vivid',
    label: 'Vivid',
    description: 'Bolder, more saturated tones — still validated and soft-professional, just easier to spot at a glance on a busy dashboard.',
    hex: {
      blue: '#1c4f97',
      teal: '#20b691',
      violet: '#8c28bd',
      amber: '#dc9b18',
      rose: '#d92662',
      emerald: '#24a83a',
      indigo: '#382bca',
      terracotta: '#dc5a18',
      ...SHARED_HEX,
    },
  },
  'high-contrast': {
    name: 'high-contrast',
    label: 'High Contrast',
    description: 'Darker tones that clear 3:1 contrast against the card background on every slot, not just where a chart also shows labels. Best if you rely on color alone.',
    hex: {
      blue: '#1c4f97',
      teal: '#259377',
      violet: '#7f30a6',
      amber: '#9a711d',
      rose: '#a12b52',
      emerald: '#238b34',
      indigo: '#4339ac',
      terracotta: '#a34b1f',
      ...SHARED_HEX,
    },
  },
}

export const CHART_THEME_ORDER: ChartThemeName[] = ['soft', 'vivid', 'high-contrast']

const STORAGE_KEY = 'dashboard.chart-theme'
const DEFAULT_THEME: ChartThemeName = 'soft'

function isThemeName(value: string | null): value is ChartThemeName {
  return value === 'soft' || value === 'vivid' || value === 'high-contrast'
}

function readStoredTheme(): ChartThemeName {
  if (typeof window === 'undefined') return DEFAULT_THEME
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return isThemeName(stored) ? stored : DEFAULT_THEME
}

// Plain module-level store (not React context) so `tremorHex()` — called
// as an ordinary function from deep inside chart render code, sometimes
// inside .map() callbacks where a hook couldn't legally live — can always
// read the live active theme synchronously. `useChartTheme()` below is
// the reactive half: any component that renders a chart color must call
// it once so it re-renders (and its `tremorHex()` calls pick up the new
// hex values) when the theme changes elsewhere in the app.
let activeTheme: ChartThemeName = readStoredTheme()
const listeners = new Set<() => void>()

export function getActiveChartTheme(): ChartThemeName {
  return activeTheme
}

export function setActiveChartTheme(name: ChartThemeName) {
  if (name === activeTheme) return
  activeTheme = name
  if (typeof window !== 'undefined') window.localStorage.setItem(STORAGE_KEY, name)
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Subscribes the calling component to chart-theme changes. Call this once
 * in any component that renders chart colors via `tremorHex()` so it
 * re-renders when the user switches themes in Settings — `tremorHex()`
 * itself always reads the live theme, but the *component* still needs a
 * reason to re-render for that new value to actually reach the screen. */
export function useChartTheme(): ChartThemeName {
  return React.useSyncExternalStore(subscribe, getActiveChartTheme, getActiveChartTheme)
}
