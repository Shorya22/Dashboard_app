# Component catalog — production-grade dashboard

Referenced by the `dashboard-design` skill. This is the checklist of what
"complete, modern, professional" actually means in components — pull from
here rather than inventing an ad hoc component list per request.

## Navigation and shell

- Collapsible sidebar with icon-only collapsed state
- Top bar: page title, global search / Cmd+K command palette (cmdk),
  notifications bell with unread badge, user menu (avatar, dropdown:
  profile / settings / logout)
- Breadcrumbs on nested pages
- Light/dark mode toggle, persisted per user
- Responsive: sidebar collapses to a drawer below ~1024px

## KPI / summary components

- KPI card: label, big number, trend arrow + percentage delta, optional
  sparkline
- Comparison KPI card: current period vs previous period, shown side by
  side or as an inline delta
- Progress-to-target card: current value, target value, progress bar
- Status/health card: colored dot + label (e.g. "3 systems degraded")

## Charts (all via Tremor, backed by Recharts)

- Line chart — trends over time, supports multiple series
- Area chart — cumulative or stacked trends
- Bar chart — category comparison, vertical and horizontal
- Grouped/stacked bar chart — multi-series category comparison
- Donut/pie chart — part-to-whole, capped at 4-5 segments
- Combo chart — bar + line together (e.g. revenue bars + growth-rate line)
- Sparkline — inline micro-trend inside a KPI card or table row
- Funnel chart — for conversion/pipeline stages
- Heatmap / tracker grid — activity over time (e.g. daily status grid)
- Geo/choropleth map — regional data, only if the data genuinely has a
  geographic dimension; use D3 or Plotly if Tremor doesn't cover it

Every chart needs: axis labels, a legend when more than one series,
interactive tooltips on hover, and a consistent color per category (see
the color system rules in SKILL.md).

## Tables (via TanStack Table v8)

- Sortable columns (click header to sort, indicator arrow shown)
- Column filters (text search, dropdown filter, date range filter)
- Global search across all columns
- Pagination controls (page size selector, prev/next, jump to page)
- Row selection with bulk actions (export selected, delete selected)
- Expandable rows for drill-down detail
- Sticky header on scroll
- Row virtualization for any table that can exceed ~500 rows
- CSV/Excel export button
- Empty state and loading skeleton rows (not a blank table)

## Filters and controls

- Date range picker (presets: today, 7d, 30d, this quarter, custom range)
- Multi-select dropdown for categories/regions
- Toggle/segmented control for switching chart views (e.g. daily/weekly/
  monthly)
- Applied-filters chip row showing active filters with individual remove
  buttons and a "clear all"
- All filters here must propagate per the SKILL.md filter-propagation
  rule

## Feedback and state

- Skeleton loaders (shaped like the real content, not a generic spinner)
- Empty states with a short message and, where relevant, a call-to-action
- Error states with a retry action, never a raw error string
- Toast notifications for background actions (export finished, data
  refreshed)
- Inline validation messages on forms (via React Hook Form + Zod)

## Polish details that separate "prototype" from "production"

- Consistent 12px/16px/24px spacing scale, never arbitrary pixel values
- Hover and focus states on every interactive element
- Subtle entrance animation on chart/card load via Framer Motion
  (200-300ms, never longer — motion should feel instant, not showy)
- Numbers formatted with locale-aware thousands separators and fixed
  decimal precision — never a raw floating-point number on screen
- Consistent icon set throughout (pick one icon library, e.g. Lucide,
  and don't mix in a second one)
- Keyboard accessible: tab order makes sense, Cmd+K opens search, Esc
  closes dialogs
