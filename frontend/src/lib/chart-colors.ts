// Single source of truth for category -> Tremor color mapping so the same
// category (e.g. "EMEA", "GCC") always renders in the same color across
// every chart on every page, per the dashboard-design skill's color rules.

// The app's categorical palette: brand blue plus 7 light, soft companion
// hues, validated with the dataviz skill's `validate_palette.js` against
// this app's actual card surface (#f8f8f9) in this fixed order — order is
// the CVD-safety mechanism (see color-formula.md), never reorder or cycle
// it. Passes lightness band, chroma floor, CVD adjacent-pair separation
// (worst ΔE 13.2, target ≥8) and the normal-vision floor (worst ΔE 20.8,
// floor ≥15) on the adjacent pairlist these charts use (bar/line/donut,
// never side-by-side scatter). Teal, amber, and emerald sit under the 3:1
// contrast target against the light surface (2.0–2.4:1) at this lightness
// — legal as a WARN only because every chart carrying these colors also
// ships a relief channel (permanent value labels and/or a named legend),
// never color alone; verified true for every chart in this app (bar charts
// always render LabelList by default, every donut always shows its
// legend). Deliberately light/pastel and low-saturation throughout — a
// calm, production-grade professional palette, not a highlighter one. If
// you need more contrast for a *new* chart that has neither labels nor a
// legend, don't reach for these slots — add direct labels/legend first, or
// fall back to brand blue.
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
}

// Seniority Category — used on the Home page's "GCC vs Non-GCC" donut
// and other workforce breakdowns.
export const SENIORITY_CATEGORY_COLORS: Record<string, string> = {
  Senior: 'blue',
  Lead: 'teal',
  Mid: 'violet',
  Other: 'amber',
  TBD: 'slate',
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

// Hex equivalents for the color tokens used above. Needed by the custom
// Recharts-based components (bar/line/donut), which take raw hex, not a
// Tremor token string. `blue`/`teal`/`violet`/`amber`/`rose`/`emerald`/
// `indigo`/`terracotta` are the validated 8-slot categorical set (see file
// header); `slate`/`gray` stay a plain muted neutral for "TBD"/"Other"/
// "Inactive" buckets, which intentionally sit outside the categorical
// rotation. Remaining legacy tokens are kept only for any code not yet
// migrated off them.
export const TREMOR_HEX: Record<string, string> = {
  blue: '#1c4f97',
  teal: '#4fc4a7',
  violet: '#9e57c1',
  amber: '#c89b41',
  rose: '#c3557a',
  emerald: '#4abf5d',
  indigo: '#6057c1',
  terracotta: '#c86e41',
  slate: '#64748b',
  gray: '#6b7280',
  red: '#b8504f',
  sky: '#0ea5e9',
  cyan: '#06b6d4',
  orange: '#f97316',
  lime: '#84cc16',
  fuchsia: '#d946ef',
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
