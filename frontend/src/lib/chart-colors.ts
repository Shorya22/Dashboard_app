import { CHART_THEMES, getActiveChartTheme } from './chart-theme-store'

// Single source of truth for category -> Tremor color mapping so the same
// category (e.g. "EMEA", "GCC") always renders in the same color across
// every chart on every page, per the dashboard-design skill's color rules.
//
// The maps below deal in TOKEN NAMES ('blue', 'teal', ...), not hex — the
// actual hex each token resolves to lives in chart-theme-store.ts as one of
// a few pre-validated, user-switchable themes (Settings page), each run
// through the dataviz skill's `validate_palette.js` against this app's
// real card surface. Switching themes there changes every chart's actual
// colors at once without touching any of these category->token maps.
//
// One series/one metric across categories (e.g. "Total Hours by Region")
// stays a SINGLE hue for that whole chart — recoloring every bar by its
// own category would spend the identity channel re-encoding what bar
// length already shows. Variety instead comes from different CHARTS each
// drawing a different single slot, and from genuinely multi-series/stacked
// charts (Client vs Internal Hours, Joiners vs Exits, seniority stacks)
// giving each series its own slot.
export const PRIMARY_COLOR = 'blue' // brand accent — default single-series color

// Region colors — stable across Home / Workforce / Skills pages
export const REGION_COLORS: Record<string, string> = {
  AMER: 'blue',
  EMEA: 'teal',
  APAC: 'violet',
  Hexaware: 'amber',
  'Region TBD': 'slate',
}

export const TYPE_COLORS: Record<string, string> = {
  GCC: 'blue',
  'Non GCC': 'slate',
}

export const WORKFORCE_CATEGORY_COLORS: Record<string, string> = {
  Active: 'blue',
  'Strategic Pool': 'teal',
}

export const STATUS_COLORS: Record<string, string> = {
  Active: 'blue',
  Inactive: 'slate',
  // Matches WORKFORCE_CATEGORY_COLORS' "Strategic Pool" — added
  // 2026-07-17 alongside the same Status value in the source roster
  // (two blank-DOJ(DEPT) employees reclassified from "Active"). Same
  // category, same color, wherever it appears.
  'Strategic Pool': 'teal',
}

// Seniority Category — used on the Home page's "Workforce by Seniority" donut
// and other workforce breakdowns.
export const SENIORITY_CATEGORY_COLORS: Record<string, string> = {
  Senior: 'blue',
  Lead: 'teal',
  Mid: 'violet',
  Other: 'amber',
  TBD: 'slate',
}

// Experience Band — used on the Skills & Experience page's "Skill
// Bifurcation by Experience" stacked bar. Explicit, not hash-derived: the
// hash fallback in `colorForLabel` below collided for "8+ Years" and
// "3-5 Years" (both landed on the same palette slot), rendering two
// distinct bands in the same color in every stacked bar's legend/tooltip.
export const EXPERIENCE_BAND_COLORS: Record<string, string> = {
  '0-1 Years': 'blue',
  '1-3 Years': 'teal',
  '3-5 Years': 'violet',
  '5-8 Years': 'amber',
  '8+ Years': 'rose',
}

export const VOLUNTARY_COLORS: Record<string, string> = {
  Voluntary: 'blue',
  Involuntary: 'terracotta',
}

// Utilization portal — Client Hours and Internal Hours are two genuinely
// separate series wherever they appear together (weekly trend, per-project,
// per-employee), so they always get two distinct hues, never blue-vs-neutral.
export const HOURS_TYPE_COLORS: Record<string, string> = {
  'Client Hours': 'blue',
  'Internal Hours': 'teal',
  client_hours: 'blue',
  internal_hours: 'teal',
}

export const UTILIZATION_SPLIT_COLORS: Record<string, string> = {
  High: 'blue',
  Moderate: 'teal',
  Low: 'slate',
}

// The 8-slot validated categorical rotation (see file header) — order
// matters, never reorder or cycle a subset.
export const CATEGORY_COLORS = [
  'blue',
  'teal',
  'violet',
  'amber',
  'rose',
  'emerald',
  'indigo',
  'terracotta',
] as const

/** Deterministic color for an arbitrary category label not covered by a
 * dedicated map above (e.g. skill names, working entities). */
export function colorForLabel(label: string, palette: readonly string[] = CATEGORY_COLORS): string {
  let hash = 0
  for (let i = 0; i < label.length; i++) hash = (hash * 31 + label.charCodeAt(i)) >>> 0
  return palette[hash % palette.length]
}

export function colorsForLabels(labels: string[], known?: Record<string, string>): string[] {
  return labels.map((l) => known?.[l] ?? colorForLabel(l))
}

// Resolves a color token ('blue', 'teal', ...) to a real hex value under
// whichever chart theme is currently active (see chart-theme-store.ts —
// Settings page lets the user switch between a few pre-validated presets).
// Needed by the custom Recharts-based components (bar/line/donut), which
// take raw hex, not a Tremor token string. Any component calling this
// during render must also call `useChartTheme()` once so it re-renders
// when the theme changes — this function alone only guarantees the *value*
// is always current, not that anything re-reads it.
export function tremorHex(token: string): string {
  const theme = CHART_THEMES[getActiveChartTheme()]
  return theme.hex[token] ?? theme.hex.gray
}

// Market (EC) display-label alias — business-confirmed remap (2026-07-16).
// The raw `Market (EC)` values from the data (`BN`, `Technology`, `DACH`,
// `UKI`) don't match the labels the approved Power BI reference uses
// (`BENO`, `AMER`, `DACH`, `UKI`). This is DISPLAY-ONLY: apply it wherever
// a market value is rendered to a user (filter dropdown labels, chart
// axis/bar labels), but always submit/compare the raw value (`BN`,
// `Technology`) to the API and in filter state — the underlying data is
// correct and untouched, only the label shown changes. `DACH` and `UKI`
// are already correct and intentionally omitted.
export const MARKET_DISPLAY_ALIASES: Record<string, string> = {
  BN: 'BENO',
  Technology: 'AMER',
}

export function marketDisplayLabel(rawMarket: string): string {
  return MARKET_DISPLAY_ALIASES[rawMarket] ?? rawMarket
}
