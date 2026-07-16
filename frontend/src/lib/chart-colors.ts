// Single source of truth for category -> Tremor color mapping so the same
// category (e.g. "EMEA", "GCC") always renders in the same color across
// every chart on every page, per the dashboard-design skill's color rules.

// Hexaware blue/indigo is the confirmed DOMINANT brand color as of the
// 2026-07-16 design pass (main series, primary donut segments, KPI icon
// default, nav/header accent). DEPT orange is now a minimal, deliberate
// identity accent reserved for the DEPT logo itself / at most one small
// badge — it is intentionally excluded from chart series and repeated
// chrome. See dashboard-design/brand-colors.md.
// Note: Tremor only accepts its own named Tailwind color tokens here (no
// arbitrary hex), so 'indigo' is the closest built-in token to the
// confirmed #3C2CDA hex — CSS-variable-driven chrome (sidebar, buttons,
// header) uses the exact hex, but chart series color is limited to
// Tremor's palette. Saturated tokens (orange, amber, fuchsia) are avoided
// in category rotations in favor of softer blue-family tones for
// readability, while keeping every category visually distinct.
export const PRIMARY_COLOR = 'indigo' // primary metric accent, reused everywhere

// Region colors — stable across Home / Workforce / Skills pages
export const REGION_COLORS: Record<string, string> = {
  AMER: 'indigo',
  EMEA: 'sky',
  APAC: 'cyan',
  Hexaware: 'violet',
  'Region TBD': 'gray',
}

export const TYPE_COLORS: Record<string, string> = {
  GCC: 'indigo',
  'Non GCC': 'slate',
}

export const WORKFORCE_CATEGORY_COLORS: Record<string, string> = {
  Active: 'indigo',
  'Strategic Pool': 'sky',
}

export const STATUS_COLORS: Record<string, string> = {
  Active: 'emerald',
  Inactive: 'red',
}

// Seniority Category — used on the Home page's "GCC vs Non-GCC" donut
// (a Power BI source-title/legend mismatch we replicate as-is, see
// dashboard-design skill notes) and Workforce/Skills pages.
export const SENIORITY_CATEGORY_COLORS: Record<string, string> = {
  Senior: 'indigo',
  Lead: 'sky',
  Mid: 'cyan',
  Other: 'violet',
  TBD: 'gray',
}

export const VOLUNTARY_COLORS: Record<string, string> = {
  Voluntary: 'amber',
  Involuntary: 'red',
}

// Utilization portal — Client Hours is the dominant blue metric,
// Internal Hours is the secondary/neutral slate, stable everywhere.
export const HOURS_TYPE_COLORS: Record<string, string> = {
  'Client Hours': 'indigo',
  'Internal Hours': 'slate',
  client_hours: 'indigo',
  internal_hours: 'slate',
}

export const UTILIZATION_SPLIT_COLORS: Record<string, string> = {
  High: 'emerald',
  Moderate: 'amber',
  Low: 'red',
}

export const CATEGORY_COLORS = [
  'indigo',
  'sky',
  'cyan',
  'violet',
  'slate',
  'blue',
  'emerald',
  'rose',
  'lime',
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
  orange: '#f97316',
  indigo: '#6366f1',
  amber: '#f59e0b',
  cyan: '#06b6d4',
  gray: '#6b7280',
  emerald: '#10b981',
  red: '#ef4444',
  violet: '#8b5cf6',
  lime: '#84cc16',
  fuchsia: '#d946ef',
  blue: '#3b82f6',
  rose: '#f43f5e',
  sky: '#0ea5e9',
  slate: '#64748b',
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
