// Single source of truth for category -> Tremor color mapping so the same
// category (e.g. "EMEA", "GCC") always renders in the same color across
// every chart on every page, per the dashboard-design skill's color rules.

// Hexaware blue is the core brand color for dashboards and metrics.
// This file intentionally keeps the palette soft and blue-led, with
// orange/amber limited to rare accent use and red reserved for negative
// status only. The goal is a cleaner, calmer UI with strong brand
// consistency and better chart readability.
export const PRIMARY_COLOR = 'blue' // primary metric accent, reused everywhere

// Region colors — stable across Home / Workforce / Skills pages
export const REGION_COLORS: Record<string, string> = {
  AMER: 'blue',
  EMEA: 'sky',
  APAC: 'cyan',
  Hexaware: 'violet',
  'Region TBD': 'slate',
}

export const TYPE_COLORS: Record<string, string> = {
  GCC: 'blue',
  'Non GCC': 'slate',
}

export const WORKFORCE_CATEGORY_COLORS: Record<string, string> = {
  Active: 'blue',
  'Strategic Pool': 'sky',
}

export const STATUS_COLORS: Record<string, string> = {
  Active: 'blue',
  Inactive: 'slate',
}

// Seniority Category — used on the Home page's "GCC vs Non-GCC" donut
// and other workforce breakdowns. The palette stays soft and avoids
// overly bright reds/oranges where possible.
export const SENIORITY_CATEGORY_COLORS: Record<string, string> = {
  Senior: 'blue',
  Lead: 'sky',
  Mid: 'cyan',
  Other: 'violet',
  TBD: 'gray',
}

export const VOLUNTARY_COLORS: Record<string, string> = {
  Voluntary: 'blue',
  Involuntary: 'slate',
}

// Utilization portal — Client Hours is the dominant blue metric,
// Internal Hours is the secondary neutral visual tone.
export const HOURS_TYPE_COLORS: Record<string, string> = {
  'Client Hours': 'blue',
  'Internal Hours': 'slate',
  client_hours: 'blue',
  internal_hours: 'slate',
}

export const UTILIZATION_SPLIT_COLORS: Record<string, string> = {
  High: 'blue',
  Moderate: 'sky',
  Low: 'slate',
}

export const CATEGORY_COLORS = [
  'blue',
  'sky',
  'cyan',
  'violet',
  'indigo',
  'slate',
  'emerald',
  'gray',
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

// Hex equivalents (Tailwind default `-500` shade, matching Tremor's own
// token -> hex mapping at that shade) for the Tremor color tokens used
// above. Needed only by custom Recharts-based components (Tremor's own
// <LineChart>/<DonutChart> take the token strings directly and resolve
// them internally) so custom charts render in the exact same colors as
// the Tremor charts next to them.
export const TREMOR_HEX: Record<string, string> = {
  indigo: '#6366f1',
  blue: '#3b82f6',
  sky: '#0ea5e9',
  cyan: '#06b6d4',
  violet: '#8b5cf6',
  slate: '#64748b',
  gray: '#6b7280',
  emerald: '#10b981',
  red: '#ef4444',
  amber: '#f59e0b',
  orange: '#f97316',
  lime: '#84cc16',
  fuchsia: '#d946ef',
  rose: '#f43f5e',
}

export function tremorHex(token: string): string {
  return TREMOR_HEX[token] ?? '#6b7280'
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
