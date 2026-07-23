# Dashboard Filters — how each dropdown gets its options

Companion to `docs/METRICS.md`. That doc explains how each number is
calculated; this one explains where the *filter option lists* on top of
those numbers come from — which column feeds each dropdown, and which
data source is canonical when there's more than one.

**Progress**

| Page group | Status |
|---|---|
| HR pages (HR Home, HR Analytics, Workforce, Skills & Experience, Employee Directory) | ✅ documented in METRICS.md "Page filters" |
| Utilization Home | ✅ Region/Market, Month/Week, Department, Hours Type |
| Utilization Search / Results | ✅ same source as Utilization Home, page uses booking-only Team / Holding filters |

**Rule we follow:** the *definition* of a filter (label, hierarchy,
column-role binding, page mapping, whether it's derived from a chart's
own bucketing) lives in YAML. The *values* the dropdown shows come from
live data at request time, so a new region or department shows up in
the filter as soon as it appears in a file — no config edit, no deploy.

## Where the config lives

Filter DEFINITIONS live in YAML for BOTH datasets now (Phase 3):

- Roster (HR pages): `backend/app/services/configs/roster_metrics.yaml`
  under `filters:`
- Booking (Utilization pages):
  `backend/app/services/configs/booking_metrics.yaml` under `filters:`
  (also declares a `columns:` block mapping filter column roles to
  physical column names)

Both blocks use the same shape:

```yaml
filters:
  <filter_key>:
    label: "Human Label"
    type: single | multi | hierarchical
    column_role: <role>            # -> columns: block; OR:
    derived_from_chart: <chart>    # for chart-derived filters
    nests: <other_filter_key>      # declares hierarchy
    applies_to_pages: [<slug>, ...]
```

The frontend reads these definitions via
`GET /api/v1/config/filters?dataset=roster|booking` (see
`backend/app/api/config.py`) through the `useFilterConfig` hook in
`frontend/src/lib/filter-config.ts`. Labels/hierarchy/page-mapping
cache indefinitely per session — they change only on a YAML edit.

## Definitions vs option values — where each lives

| What | Where it lives | Who can change it |
|---|---|---|
| Which column feeds each HR-page filter, and how it derives (raw / chart-derived) | `backend/app/services/configs/roster_metrics.yaml` under `filters:` | Config edit, no code |
| Which columns feed each Utilization-page filter (label, hierarchy, page mapping) | `backend/app/services/configs/booking_metrics.yaml` under `filters:` | Config edit, no code |
| Which columns feed the Utilization filter *option lists* and which are unioned across roster + booking | `backend/app/services/booking_metrics.py::get_filter_options` | Developer |
| The actual dropdown option values (Active, EMEA, QA, "13 Apr 2026", …) | Live data — `distinctValues(...)` at request time, never a hardcoded list | Whoever uploads the next roster / booking file |

## Canonical source per Utilization filter

Two source files feed the Utilization pages: the roster (employee
attributes) and the booking sheet (per-employee/day/project hours).
Each filter field picks the source that makes it correct — and, where
both sources have a compatible column, unions them so the dropdown
shows every real value.

| Filter (Utilization Home) | Source | Column(s) | Why |
|---|---|---|---|
| Region | ROSTER ∪ booking | roster.`Region` ∪ booking.`Region (EC)` | Region is an employee attribute; the roster is the master workforce list. A region present only in the roster (e.g. `APAC`, `Region TBD`) still appears — the user sees every real value. Picking a roster-only region filters booking rows to zero, which is acceptable and matches "show all options" intent. |
| Market | ROSTER ∪ booking | roster.`Market` ∪ booking.`Market (EC)` | Same rationale as Region. Markets under each region are unioned in the `region_market_hierarchy` used by the Region/Market hierarchical select. |
| Department | ROSTER ∪ booking | roster.`Designation` ∪ booking.`Department` | The roster's canonical department column is `Designation` — the DAX "Departments" measure is `DISTINCTCOUNT(HR MASTER[Designation])` (confirmed in the data-model skill and `docs/METRICS.md` under "Card: Departments"). Booking's `Department` (coarser: Engineering, QA, Creative Content, …) is unioned defensively in case booking has a value the roster doesn't. |
| Month / Week | Booking-only | booking.`Monday of Week`, booking.`Month` | Weeks are the booking sheet's own reporting cadence. The frontend builds Year>Month>Week labels from the ISO week-start Monday — the backend's `month` string is a raw datetime and MUST NOT be used for display (see `frontend/src/lib/utilization-api.ts::weekHierarchyToItems`). |
| Entity (Team) | Booking-only | booking.`Team (EC)` | Booking-specific internal team code (e.g. `CMUS`). No roster counterpart. |
| Holding | Booking-only | booking.`Holding` | The booking sheet's clean, one-per-row client field. Booking-specific by design. |
| Hours Type | Booking-only | booking.`Booked Hours Type` | `Client Hours` / `Internal Hours`. No roster counterpart. |

> These are the runtime option lists returned by
> `GET /api/v1/utilization/filter-options`
> (`booking_metrics.get_filter_options(booking_df, roster_df)`). The
> route passes the cached roster in so the union is applied
> consistently on every request — see
> `backend/app/api/utilization.py`.

## Design rules that keep the Utilization filters honest

- **Union, don't switch.** A roster-only region and a booking-only region
  both appear in the dropdown. Silently preferring one source over the
  other would hide real values the user can legitimately want to filter
  by. Picking a value that has no booking rows returns an empty result
  set — visible, honest, and self-explanatory.
- **Blank / whitespace values are dropped once, at the source.**
  `_clean_str` in `booking_metrics.py` trims and treats an empty result
  as absent. This means `"EMEA"`, `" EMEA "`, and `"EMEA\n"` all fold
  into a single dropdown entry — the same case-normalisation guarantee
  METRICS.md documents for HR pages, applied here at the option-list
  build step.
- **The value the user picks is the value the API compares against.**
  For flat fields (Region, Market, Department, Entity, Holding, Hours
  Type) the dropdown emits the raw string exactly as returned by
  `get_filter_options` — no re-labelled or aliased value the server
  wouldn't recognise. The Region/Market hierarchical select uses
  composite `"<region>::<market>"` values so a Market selection
  round-trips through `splitRegionMarketSelection` back into
  `region[]` / `market[]` query params.
- **Date labels are derived on the frontend from the ISO week-start
  Monday**, not from any backend-emitted display string — because the
  booking sheet's `Month` column is a real `datetime64`, and its
  Python-side string coercion would leak raw `"2026-04-26 00:00:00"`
  values into the label if trusted. See
  `weekHierarchyToItems` and the shared `WEEK_MONTH_FMT` /
  `WEEK_DAY_FMT` formatters — the same style used by
  `weeksToHierarchy` in `utilization-search-page.tsx` and
  `employee-utilization-page.tsx`.
- **The `HierarchicalMultiSelect` component is arbitrary-depth.** Year
  > Month > Week and Region > Market both use the same tree-select;
  synthetic parent nodes carry `isGroup: true` so their `value` is
  never emitted as a filter param, only the descendant leaves are.

## Known data-quality issues

These are visible in the dropdowns today because the filter design
shows real values rather than silently hiding them — the user needs to
see what their upload actually contains. Each is a data fix (edit the
source file) rather than a code fix.

### The Department dropdown contains job-title-like values

The Department dropdown unions **roster `Designation` + booking
`Department`**, matching the "Departments" DAX measure
(`DISTINCTCOUNT(HR MASTER[Designation])`). The roster's `Designation`
column is intended to be a job title (per the data-model skill and
`docs/METRICS.md`'s "Card: Departments" note — "this counts distinct
job titles, not organisational departments"), and the current file
mixes coarse department-like labels (`Engineering`, `QA`,
`Creative Content`) with fine-grained role-like labels
(`BE Salesforce Commerce cloud Developer`,
`Front end developer - React Senior`).

Both kinds are legitimate values of the same column — the roster has
never enforced a distinction between "team/department" and "role/title"
in `Designation` — so the filter surfaces both. Filtering by a
role-like value that has no booking hours yields an empty result, at
which point the Weekly Hours Trend on Utilization Home shows a
filter-aware message ("No booking hours match the selected filters. Try
clearing a filter.") rather than the generic "No data for this view",
so the user has an obvious next step.

**How to fix it in the source:** clean the `Designation` column in
`backend/data/DEPT - Master Data(Sheet1).xlsx` so each value is either
consistently a department or consistently a role — this is a data
edit, not a code change. Once cleaned, the dropdown updates on the
next upload; no config or code change needed.

## Consistency rules we enforce automatically

Backend regression tests, in `backend/tests/test_booking_metrics.py`:

| Test | Guarantees |
|---|---|
| `test_get_filter_options_region_market_hierarchy_unions_roster_and_booking` | Region hierarchy contains every region from either source; markets under each region are unioned; blank/whitespace values are dropped; the flat `regions` / `markets` lists reflect the same union. |
| `test_get_filter_options_departments_unions_roster_designation_and_booking_department` | `departments` filter list is the union of roster `Designation` and booking `Department`, alphabetically sorted, blanks dropped. |
| `test_get_filter_options_entities_holdings_hours_types_are_booking_only` | Passing a roster in does NOT change `entities` / `holdings` / `hours_types` — these stay booking-only regardless of roster content. |
| `test_get_filter_options_union_invariants` | For any (booking, roster) pair, `regions` / `markets` / `departments` returned by `get_filter_options` equal the set-union of the two source columns' cleaned distinct values. |
| `test_real_bookings_filter_options_with_roster` | Same invariants, against the real roster + booking fixtures. |

Each exists because of a real user-visible bug: Utilization Home's
Region filter showing only `AMER` / `EMEA` while the HR pages carried
the full 4-region set, and the same shape of bug re-surfaced for
Department — both fixed together by making the union the contract
instead of switching source per field.
