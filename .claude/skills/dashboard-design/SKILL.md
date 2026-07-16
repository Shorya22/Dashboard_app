---
name: dashboard-design
description: Use whenever creating, editing, or reviewing any dashboard screen, chart, KPI card, filter, or data table in the frontend. Covers chart-type selection, color system, layout grid, and how filters propagate across a page. Also use when checking a built screen against the Power BI reference screenshots in reference/.
---

# Dashboard design conventions

This is the single source of truth for how any dashboard screen should look
and behave. Follow it instead of deciding styling fresh on each request.

## Libraries (do not substitute)

- Charts and KPI cards: **Tremor** (built specifically for analytics
  dashboards — area/bar/donut charts, KPI cards, sparklines, delta
  indicators, all on Tailwind, light/dark out of the box)
- General UI (buttons, dialogs, dropdowns, command palette, date pickers):
  **shadcn/ui** — copy-paste, owned code, built on Radix primitives so
  accessibility isn't bolted on later
- Data tables: **TanStack Table v8** — the modern default for sortable,
  filterable, paginated tables with CSV export and row virtualization
- Forms: **React Hook Form + Zod** — type-safe validation
- Subtle motion: **Framer Motion** — page transitions, card hover states,
  chart entrance animation. Motion is a polish layer, never load-bearing
  for functionality.
- Command palette: **cmdk** (Cmd+K quick navigation/search) — expected in
  any 2026 "modern SaaS" dashboard, cheap to add, high perceived polish
- Layout and spacing: **Tailwind CSS**
- Data fetching: **TanStack React Query**

If a requested component isn't available in Tremor/shadcn, build it with
Tailwind directly — don't pull in a different charting or UI library.
For structural reference, the shadcn/ui dashboard example (sidebar +
KPI cards + Recharts) and TailAdmin's component set are the closest
free, current templates to what "modern professional dashboard" means
in 2026 — use them as a visual reference point, not a dependency.

See `component-catalog.md` in this folder for the full list of
components, chart types, and table features expected in a production
dashboard.

## Chart-type rules

- Trend over time → line chart
- Comparing categories → bar chart
- Part-to-whole → stacked bar chart. Never a pie/donut chart beyond 4
  categories — they're hard to read past that.
- A single important number → KPI card with a small trend indicator
  (up/down arrow + percentage), not a chart
- Underlying detail behind a summary number → clicking the summary opens
  a detail table (drill-down), it does not replace the chart in place

## Color system

- One accent color for the primary metric across all charts on a page
  (pick one brand color and reuse it everywhere that metric appears)
- Gray for neutral/comparison series
- Green only for positive deltas, red only for negative deltas — never
  use red/green for anything else (avoids false "good/bad" signals)
- Every chart on the same page uses the same color for the same category
  (e.g. "North" region is always the same color in every chart)

## Layout grid

- Sidebar: fixed width, icon + label nav items
- Top bar: page title left, filters/date range right
- KPI row: 3-4 cards per row, equal width, `gap: 12px`
- Chart grid below KPIs: 2 columns on desktop (a wide primary chart +
  narrower secondary chart), 1 column on narrower viewports
- Data tables go full width below the chart grid, never beside a chart

## Filters must propagate

Any filter (date range, region, category) in the top bar must update
every chart and table on the page — never build a filter that only
affects one chart. Implement this with a shared filter state (React
Context or a query-param-backed store) that all chart components read
from, not local component state.

## Loading and empty states

- Every chart/table shows a skeleton placeholder while loading — never a
  blank space or a spinner with nothing else
- Every chart handles the "no data for this filter" case explicitly with
  a short message, not a blank chart area

## Checking work against the Power BI reference

Reference screenshots of the approved Power BI dashboard live in
`reference/` next to this file. When building or reviewing a screen,
compare against them for: chart type choice, which metrics are grouped
together, and overall information density — not exact pixel layout,
since the web version should look more modern, not identical.
