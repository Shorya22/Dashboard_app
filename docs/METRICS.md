# Dashboard Metrics — how every number is calculated

How each card and chart gets its number, in plain terms. Written page by
page as we verify them; anything not listed here has not been reviewed yet.

**Progress**

| Page | Status |
|---|---|
| Home | ✅ 3 cards + 4 charts |
| HR Home (HR Portal) | ✅ all 4 cards + 4 charts verified |
| HR Analytics | ✅ 5 cards + 4 charts (Attrition % is a formula — see below) |
| Workforce | ✅ 6 cards + 3 charts verified |
| Skills & Experience | ✅ 3 cards + 4 charts verified |
| Employee Directory | ✅ config-driven columns + Serial No. |
| Utilization Home | ✅ 5 cards + 2 charts |
| Utilization Search / Results | ✅ form + 5 cards + records table |
| Utilization Overview | ✅ 3 cards + 3 charts (booking-derived Formula A) |
| Employee Utilization drill-through | ✅ 4 cards + 2 charts + records table |
| Project Utilization drill-through | ✅ 4 cards + 2 charts + detail table |

Figures below were checked against the live data on 2026-07-22 (roster 52
rows, booking 2,961 rows) and are shown only to make the rules concrete —
they move with the data; the rules don't.

**Rule we follow:** one business concept = one definition, in one place.
If the same label appears on two pages it must resolve to the same
function, never be recomputed separately. That is what caused the
"Strategic Pool showed 1 on Home and 3 on HR Home" bug.

**Where the rules live:**

| What | Where | Who can change it |
|---|---|---|
| What a valid upload looks like (columns, types) | `backend/app/services/validation/configs/*.yaml` | Config edit, no code |
| Which column plays which role, and what each card counts | `backend/app/services/configs/roster_metrics.yaml` | Config edit, no code |
| What the values *mean* (status, seniority keywords, hours labels) | `backend/app/services/configs/*_metrics.yaml` | Config edit, no code |
| Which column holds the joining/leaving date, and the leaving-reason values | `backend/app/services/configs/roster_metrics.yaml` | Config edit, no code |
| Which charts exist and what each one plots (`charts:`) | `backend/app/services/configs/roster_metrics.yaml` | Config edit, no code |
| A genuinely new *kind* of chart (a new `type:`) | `backend/app/services/roster_metrics.py` | Developer |

**The two things deliberately still in code**, and why:

| | Why not config |
|---|---|
| **Attrition %** | It is arithmetic — `Exits ÷ (Closing + Exits)`. Expressing formulas in YAML means inventing operators and precedence in a config file: harder to read and debug than the Python it replaced. Its *inputs* are config-driven. |
| **Closing Headcount (per month)** | The headline CARD is declared (`status_filter: present`) — at full range the joining-date test excludes nobody, so it is simply the present workforce. Only the per-month values behind the growth trend walk the calendar, and that walk is an algorithm. |

Everything else on Home, HR Home and HR Analytics — 25 of 26 cards and
charts — is declared in YAML. Attrition % is the only one that is not.

### The config validates itself

`roster_metrics.yaml` is hand-edited, so it is checked when it loads
rather than when someone opens a page. A typo used to surface as a
KeyError mid-request — a 500 with a stack trace instead of an
explanation. Now it fails at startup naming the exact problem:

```
roster_metrics.yaml is invalid:
  - cards.projects: column_role 'clientt' is not defined in `columns:`
    (known: ['client', 'designation', 'employee_id', ...])
```

Checked: every `column_role` exists; every `status_filter` names a real
status; every `derived_from_chart` names a real chart; chart `type` and
`scope` are ones the engine implements; a `numeric_bands` chart ends with
a catch-all band (otherwise values above the last threshold vanish); each
`monthly_series` series has exactly one of `measure`/`date_role`; and
every `counts_as_present` value is a declared status.

### Column roles

Metrics never reference a raw column heading; they reference a **role**,
resolved through config:

| Role | Column | Used by |
|---|---|---|
| `employee_id` | `NEW_EMP_ID` | every headcount (counted distinctly) |
| `employee_name` | `NAME` | Employee Directory |
| `designation` | `Designation` | Departments card |
| `client` | `Client` | Projects card |
| `status` | `Status` | Active / Strategic Pool / Closing Headcount, Status Split |
| `region` | `Region` | Headcount by Region |
| `working_entity` | `Working Entity` | Workforce by Working Entity |
| `seniority` | `Seniorirty Level` | Workforce by Seniority |
| `experience_total` | `Total Experience` | Workforce by Experience Band |
| `primary_skill` | `Primary Skill` | Skills pages, Skill filter |
| `employment_type` | `Type` | GCC vs Non GCC, Type filter |
| `joining_date` | `DOJ (DEPT)` | Joiners, Month Wise Headcount |
| `leaving_date` | `LWD` | Leavers, Month-Wise Resignation |
| `leaving_reason` | `Reason for Leaving` | Voluntary vs Involuntary |
| `snapshot_date` | `Today` | calendar range |

**Headings that carry a reporting period.** The client column used to be
exported as `Client as on June 2026` — a heading that changes every
month, which would have failed the required-column check on every new
export. Two things now protect against that:

1. The source has been changed to export a stable `Client` heading.
2. The contract also matches the old shape by **pattern**
   (`matches: "Client as on .*"`) and renames it to `Client` on read.

So `Client`, `Client as on June 2026`, `Client as on July 2026` and any
future period are all accepted, with no config or code change. Older
files already uploaded keep working. Locked in by
`test_client_column_heading_may_carry_any_period`.

Use the same `matches:` mechanism for any other heading that starts
carrying a date.

### The app is not case-sensitive

Values that differ only by capitalisation are treated as the same value.
This matters because casing used to fail **silently**:

| If the source were typed... | Before | Now |
|---|---|---|
| `Status` in lower case | every headcount card read **0** | correct |
| `Booked Hours Type` in lower case | donut **empty** | correct |
| `Region` mixed case | `EMEA` and `emea` as two bars | one bar |

22 columns are marked `normalize_case: true` (14 roster, 8 booking) —
every column used for an equality comparison or a group-by.

Variants fold onto a **canonical spelling** rather than being re-cased,
because blunt title-casing would mangle the acronyms this data is full of
(`GCC` → "Gcc", `EMEA` → "Emea"):

1. Columns compared by equality declare `canonical_values` — `Status`,
   `Type`, `Reason for Leaving`, `Booked Hours Type`. So even a file
   typed entirely in lower case resolves to `"Active"`, because the
   correct spelling comes from config rather than from the file.
2. Every other column folds to the **most common spelling already in the
   file**, which preserves acronyms exactly as the business writes them.

This is applied at ingestion, so it protects cards, charts, filters and
group-bys alike.

**Not reported to the admin.** `"EMEA"` and `"emea"` unambiguously mean
the same thing, so nothing is guessed and there is nothing to act on —
flagging it would be noise about a problem already solved. It is logged
server-side for traceability. Contrast with a defaulted blank, which
*does* assert a fact the file didn't contain and is warned about.

---

## Data sources

| Source | File | Drives |
|---|---|---|
| Roster | `DEPT - Master Data(Sheet1).xlsx` | Headcount, status, seniority, experience |
| Booking | `UTILIZATION DATA SHEET.xlsx` | Hours, client vs internal utilization |
| Ground truth | `PowerBI_Ready_Utilization_May_2026.xlsx` | **QA-only** (see below) — NOT a runtime input to any dashboard page |

The dashboard always reads the **latest promoted upload**; if nothing has
been uploaded it falls back to the bundled file.

**Ground truth is QA-only, not a dashboard data source.** As of
2026-07-26 no dashboard page reads `PowerBI_Ready_Utilization_May_2026.xlsx`
at runtime — Utilization Overview computes from the booking sheet using
Formula A instead (see Page 8 below). The file is only consulted by the
admin-only `GET /api/v1/qa/reconcile?dataset=utilization` diagnostic
endpoint, which checks Formula A against this file's shipped ratios. Its
upload card on the Data Management page is labelled accordingly
(`display_name`/`description` in
`backend/app/services/validation/configs/ground_truth.yaml`, rendered
verbatim by the frontend — config-driven, not hardcoded in the React
component) so uploading it never reads as required for the dashboard to
work.

---

## Page 1 — Home

Current values are from the roster of 52 rows / booking of 2,961 rows
(2026-07-22) and are shown only to make the rules concrete.

### Card: Active Employees — `35`
Employees whose **`Status` = "Active"**, counted as distinct `NEW_EMP_ID`.

### Card: Strategic Pool — `3`
Employees whose **`Status` = "Strategic Pool"**, counted as distinct
`NEW_EMP_ID`.

> Previously this was "employees with a blank `DOJ (DEPT)`", which is why
> Home (1) and HR Home (3) disagreed. It is now the `Status` column only,
> and every surface calls the same function.

### Card: Closing Headcount — `38`
**Everyone who had joined by the end of the period and is still part of
the workforce.**

- Joined = `DOJ (DEPT)` on or before the period end (a blank joining date
  still counts — the person is here, the date just wasn't recorded)
- Still here = `Status` is **Active or Strategic Pool**. **Inactive
  employees are never counted**, whether or not they have a last working
  day.

So Closing Headcount always equals Active + Strategic Pool (35 + 3 = 38).

> Previously this counted anyone without an `LWD` date, so 9 employees
> marked Inactive but missing an LWD were still counted as present — the
> card read 47 while the donut on the same page read 38.

### Chart: Month-wise Workforce Growth
Closing Headcount (rule above) computed at the end of **each month**, so
the line is purely cumulative by joining date: if May closes at 34 and 4
people join in June, June closes at 38. It never dips, because leavers
are excluded from every month rather than removed at their exit date.

Current: Jul-25 `2` → Aug `4` → Sep `7` → Oct `9` → Nov `11` → Dec `16`
→ Jan-26 `23` → Feb `26` → Mar `30` → Apr `31` → May `34` → Jun `38`.

### Chart: Workforce Category (donut) — `38`
Two slices, both from `Status`: **Active** (35) and **Strategic Pool** (3).

### Chart: Workforce by Seniority (donut) — `38`
Bands come from **keyword matching on the `Seniorirty Level` column**
(the column name's typo is in the source file and is kept deliberately).
First match wins, case-insensitive:

| If the value contains | Band |
|---|---|
| `tbd` | TBD |
| `lead` | Lead |
| `senior` | Senior |
| `mid` | Mid |
| anything else | Other |

Order matters: "Seniority TBD" contains "senior", so `tbd` is tested
first. Keywords are configured in `roster_metrics.yaml` — adding one is a
config edit.

Scope: **current workforce only** (Active + Strategic Pool), so it totals
38 and agrees with the other cards on the page.

Current: Senior `15`, Lead `13`, Mid `5`, TBD `4`, Other `1`.

### Chart: Internal v Client Utilization (donut) — `17.15K` hours
From the **booking** (utilization) sheet. The `Booked Hours Type` column
holds the category; hours are summed from `Employee Booked Hours` for
each one:

| Category (`Booked Hours Type`) | Rows | Sum of `Employee Booked Hours` | Share |
|---|---|---|---|
| Client Hours | 1,929 | **11,433.6** | 66.66% |
| Internal Hours | 1,032 | **5,719.2** | 33.34% |
| **Total** | 2,961 | **17,152.8** | 100% |

The donut's centre figure (`17.15K`) is that total. Verified 2026-07-22
directly against the raw file — Client + Internal equals the total
exactly, so no hours are unaccounted for.

The two category labels are configured in `booking_metrics.yaml`, so
renaming one is a config edit. If a **third** category ever appears
(e.g. "Leave Hours"), those hours would count toward the total but land
in neither slice — the `hours_split_covers_all_hours` invariant catches
exactly that and names the offending category.

---

## Page 2 — HR Home (HR Portal)

Card definitions are declared in `roster_metrics.yaml` under `cards:`, so
this table and the code read from the same source.

### Card: Total Employees — `52`
Distinct **`employee_id`** (`NEW_EMP_ID`). **No status filter** —
everyone in the file, whether Active, Inactive or Strategic Pool.

**What if an employee has no ID?** A blank `NEW_EMP_ID` is filled at
ingestion with a **numbered** marker — `NEW_EMP_ID TBD 1`,
`NEW_EMP_ID TBD 2`, … — so each such person is still counted once. The
numbering is not cosmetic; with the current roster (2 employees have no
ID) the alternatives both under-count:

| Design | Total Employees | Result |
|---|---|---|
| Leave blank | 50 | distinct-count ignores blanks — both people vanish |
| One shared `"NEW_EMP_ID TBD"` | 51 | both collapse into a single value |
| **Numbered markers** (what we do) | **52** ✅ | each counted once |

Every filled cell is reported as a warning on upload, and
`test_blank_ids_do_not_undercount_headcount` locks the behaviour in.
Those employees display as `NEW_EMP_ID TBD 1` in the Employee Directory
until real IDs are assigned — the count is right, the identifier is a
placeholder.

### Card: Active Employees — `35`
Distinct `employee_id` where `Status` = "Active". **Identical definition
to the Active Employees card on Home** — same function, so the two pages
cannot disagree.

### Card: Departments — `27`
Distinct values of the **`designation`** role (`Designation` column),
case-normalised so `"SalesForce Core Developer"` and `"Salesforce Core
Developer"` count once.

> Note: this counts distinct **job titles**, not organisational
> departments. Confirmed as intended.

### Card: Projects — `31`
Distinct values of the **`client`** role (the `Client` column).

Two behaviours worth knowing, both confirmed as intended:
- Cells can hold several comma-separated clients and the **whole cell**
  counts as one value — `"Barbour, PK Commerce"` is one entry, and
  `"ParsonKelloggs"` vs `"ParsonKelloggs, Barbour"` are two different ones.
- `"Client TBD"` (unallocated) is included.

*(For comparison, the booking sheet's clean one-per-row columns give 49
clients and 81 projects — a different question, answered on the
Utilization pages.)*

### Chart: Status Split (donut) — `52`
Groups by the **`Status`** column: Active `35`, Inactive `14`, Strategic
Pool `3`.

**The slices are simply whatever the column contains.** Nothing is
declared in config first — same as Home reading Active and Strategic Pool
straight from the column. A status with no rows just doesn't appear.

#### What happens if a new status shows up

Say the business starts using `"Notice Period"`:

| | |
|---|---|
| Appears in the donut | **Yes**, immediately, as its own slice — no config, no code, no deploy |
| Counted in Total Employees | **Yes** |
| Counted in Closing Headcount / "current workforce" | **No**, until someone says it should be |
| Flagged on upload | **Yes**, naming the value |

The report says:

> ⚠ new Status value(s) `['Notice Period']` — not currently counted as
> part of the workforce. If they should be, add them to
> `status.counts_as_present`

**Why it needs a decision at all:** one question can't be read off the
data — does someone with that status still count as part of the
workforce? Nothing in the file answers it, so `counts_as_present` in
`roster_metrics.yaml` holds that one business meaning:

```yaml
status:
  counts_as_present: ["Active", "Strategic Pool"]
```

To count a new status as still-here, add it to that list. To exclude it,
do nothing — it stays visible in the donut and in Total Employees, just
outside headcount.

**Why the default is "not present":** quietly *inflating* headcount is a
far worse failure than briefly under-counting with a visible warning. You
would never notice the first; you can't miss the second.

Guarded by the `every_status_has_a_workforce_meaning` invariant, which
runs in the tests and on every upload.

### Chart: Headcount by Region (bar) — `52`
Groups by the **`Region`** column. EMEA `34`, AMER `15`, APAC `1`,
Region TBD `2`.

### Chart: Workforce by Working Entity (bar) — `52`
Groups by the **`Working Entity`** column. AMER `15`, DTNL `14`,
DTIE `12`, DTDE `4`, DTUK `4`, Entity TBD `2`, DTAU `1`.

### Chart: Workforce by Experience Band (bar) — `52`
Buckets **`Total Experience`** by the thresholds declared in config.
First band the value falls under wins; boundaries are half-open:

| Band | Years |
|---|---|
| 0-1 Years | `< 1` |
| 1-3 Years | `< 3` |
| 3-5 Years | `< 5` |
| 5-8 Years | `< 8` |
| 8+ Years | everything else |

Current: `7` / `0` / `2` / `12` / `31`. Every band is returned in this
order even when empty — `1-3 Years` renders as a zero bar rather than
vanishing from the axis (the order used to be arbitrary).

> The cut-offs are **PROVISIONAL** — never confirmed against the source
> model. Change them in `roster_metrics.yaml` under
> `charts.workforce_by_experience_band.bands`.

### Blanks are counted, never dropped
A group-by silently discards blank cells, so an empty `Region` used to
make the bars total less than the headline card above them, with nothing
on screen to explain the gap. Blanks now count under the chart's
`blank_label`, matching the "TBD" convention already in the data so they
fold in with existing TBD rows rather than forming a second bucket:

| Chart | Blank becomes |
|---|---|
| Headcount by Region | `Region TBD` |
| Workforce by Working Entity | `Entity TBD` |
| Workforce by Experience Band | `Unknown` |

The `charts_account_for_everyone` invariant asserts every chart totals to
the population it describes, in tests **and** on every upload.

### Scope is declared, not accidental
Each chart states which population it describes, because it genuinely
differs between pages and that should be a visible decision:

| Page | Scope | Total |
|---|---|---|
| HR Home charts | `all` — the whole roster | 52 |
| Home's Workforce by Seniority | `present` — Active + Strategic Pool | 38 |

HR Home is headlined by Total Employees (52) and its Status Split must
show Inactive at all; Home is headlined by Closing Headcount (38).

---

## Page 3 — HR Analytics

Cards reduced from 7 to 5 (2026-07-22): **Inactive**, **Joiners** and
**Closing Headcount** were removed, and **Strategic Pool** added.

### Card: Total Employees — `52`
Same definition as HR Home: distinct `employee_id`, no status filter.

### Card: Active — `35`
Distinct `employee_id` where `Status` = "Active".

### Card: Strategic Pool — `3`
Distinct `employee_id` where `Status` = "Strategic Pool". Same definition
as the Home card.

### Card: Exits — `14`
**Exits = Inactive.** Same people, same number — confirmed with the
business, so there is one definition, not two.

> Previously Exits was counted from `LWD` dates and returned **5** while
> Inactive returned **14** — the same employees described two ways,
> because 9 of them are marked Inactive with no last working day
> recorded. Locked by the `exits_equals_inactive` invariant.

The Exits card responds to the page's filters, like the other Status
cards. (It used to read an unfiltered server value, so applying a filter
moved Active but left Exits frozen.)

### Card: Attrition % — `26.9%`
Unchanged formula: **Exits ÷ (Closing Headcount + Exits)**.
`14 ÷ (38 + 14) = 26.9%`.

> It read 11.6% before, because Exits was 5. The formula didn't change —
> only the Exits definition feeding it. Attrition is the one card here
> that is *not* filtered, because it needs Closing Headcount, which is
> date-based and not derivable from the employee rows the page filters on.

### All four charts are declared in `charts:`

Like the HR Home charts, each is defined in `roster_metrics.yaml` and
computed by the generic engine — not bespoke Python:

| Chart | Declaration |
|---|---|
| Month Wise Headcount | `monthly_series`, one `closing_headcount` measure per month |
| Monthly Joiners vs Leavers | `monthly_series`, two series: `joining_date` and `leaving_date` |
| Month-Wise Resignation | `monthly_series`, one `leaving_date` series |
| Voluntary vs Involuntary | `count_by` on `leaving_reason`, `scope: exited` |

`monthly_series` walks the dataset's month range and evaluates each
declared series per month. A series is either a **measure** (a named
metric evaluated for that month) or a **date_role** (count employees
whose date falls inside the month).

Verified config genuinely drives them: adding a third series to
Joiners vs Leavers purely in YAML made a `headcount` field appear in the
output, with no Python change.

### Chart detail: Monthly Joiners vs Leavers, Month-Wise Resignation
- **Joiners** come from **`DOJ (DEPT)`** — the month someone joined.
- **Leavers** come from **`LWD`** — the month someone left.

That is the intended logic and is unchanged.

### The one thing the data person has to keep filled in

Everyone who leaves must get an **`LWD`** and a **`Reason for Leaving`**.
Those two fields are what let a departure appear in a *month* and be
classified as Voluntary or Involuntary. Status alone can't do it — it says
someone left, not when or why.

Today 9 of the 14 Inactive employees are missing both, so:

| | Card | Charts |
|---|---|---|
| Exits | **14** | monthly leavers total **5** |
| Voluntary vs Involuntary | — | classifies **5** |

**This is a data gap, not a code one.** Verified by simulation: filling in
those 9 rows makes everything reconcile with no code change —
`get_dated_exits` becomes 14, the monthly trend totals 14, and Voluntary
vs Involuntary covers all 14.

**The upload tells the data person exactly what to fix**, both as a
summary and as a row list:

> ⚠ exits=14, of which 5 have a leaving date; 9 exit(s) have no LWD, so
> the monthly leavers trend and the Voluntary/Involuntary split cannot
> include them

> ⚠ 9 rows missing LWD — Excel rows 6, 14, 15, 21, 23, 29, 32, 35, 46
> ⚠ 9 rows missing Reason for Leaving — same rows

Both are **warnings**, never blockers: the upload still goes through and
the dashboard still works.

*Month Wise Headcount and the two charts above have not otherwise been
reviewed yet.*

---

## Page 4 — Workforce

Whole-roster composition. All six cards reuse definitions already covered
(Total 52, Active 35, Strategic Pool 3, Departments 27, Projects 31), plus:

### Card: Inactive Employees — `14`
Distinct `employee_id` where `Status` = "Inactive". **Same people, same
rule as the Exits card on HR Analytics** — declared as a separate card
only because the label differs per page. Equal by construction (same
`status_filter`), guarded by the `exits_equals_inactive` invariant.

### Chart: Headcount by Seniority — `52`
`count_by` on the **raw `Seniorirty Level`** column — every distinct value
is its own bar (Standard Lead 12, Seniority TBD 9, Standard/Premium Senior
9/8, Premium Lead 6, Premium Mid 4, Standard Mid 3, Premium TSDM 1). The
set of values can grow or shrink with the data; casing duplicates are
folded at ingestion, so no normalization lives in the chart.

### Chart: Workforce by Type — `52`
`count_by` on `Type` (GCC 49 / Non GCC 3). Blank -> "Type TBD".

### Chart: Workforce Details by Region — `52`
Reuses the **same `headcount_by_region` chart** as HR Home — AMER 15,
EMEA 34, APAC 1, Region TBD 2.

> Fixed a real bug here: the frontend previously hardcoded the region list
> as `AMER / APAC / EMEA / Hexaware`, which showed an always-empty
> **Hexaware** bar and **hid the Region TBD** employees entirely. It now
> renders whatever regions the data contains.

---

## Page 5 — Skills & Experience

### Cards
Total Employees (52) and Departments (27) reuse existing definitions.

**Skills Covered — `14`**: distinct values of the `skill` role (the broad
`Skill` column, not Primary Skill), excluding blanks and any value
containing "TBD". Declared with `exclude_containing: "TBD"`.

### Charts: the three "Skill Bifurcation" stacked bars
Each is a `crosstab` — Primary Skill (rows) x a dimension. The dimension
**reuses another chart's own bucketing** via `dimension_from_chart`:

| Chart | Dimension reused from |
|---|---|
| by Experience | `workforce_by_experience_band` (the experience bands) |
| by Seniority | `workforce_by_seniority_category` (the keyword bands) |
| by Region | `headcount_by_region` |

So "Skill Bifurcation by Experience" and the standalone experience chart
use the **same** bands by construction — change them in one place and both
move. This removed a separate Python `_experience_band` copy that agreed
today but had no guarantee of staying in step (locked by
`test_crosstab_dimension_cannot_drift_from_the_standalone_chart`).

### Chart: Total Employees by Experience Band — `7 / 0 / 2 / 12 / 31`
The standalone `workforce_by_experience_band` chart (numeric_bands),
identical to the one on HR Home.

---

## Page 6 — Employee Directory

The searchable roster table. Filtering is already server-side (via the same
YAML filters as the other pages). Two parts are now config-driven:

**The record** (`directory.fields` — output key -> column role): every field
resolves through a **role**, so a renamed source column flows through here
exactly like it does for the cards and charts. This replaced a hardcoded
column map that read raw headings and would have broken on a rename (e.g.
the client column's `Client as on <month>` heading). Locked by
`test_directory_record_follows_a_renamed_source_column`.

**The table columns** (`directory.columns` — ordered key + label + display
hint): the displayed set, order and labels come from YAML. The frontend
supplies only presentation for a `display` hint:

| `display` | Rendering |
|---|---|
| `serial` | 1-based **S.No.** counter, continuous across pages in the current sort |
| `experience` | "x yrs" |
| `grade` | grade-aware sort (G3A < G4 < …) |
| (none) | plain text |

### Serial No. (new)
A `serial_no` column, declared first in `directory.columns`. It's a display
row counter (position in the current sorted set), not stored data — so
there's nothing to configure beyond its presence and label.

Both parts are guarded: the config validator rejects a directory field
pointing at an unknown role, or a display column with no matching field, at
load time.

---

## Page 7 — Utilization Home

The first Utilization portal page — a KPI strip over the booking sheet
plus two breakdown charts. Every card and chart on this page is
declared in `configs/booking_metrics.yaml` (under `cards:` / `charts:`)
and computed by the generic dispatcher (`evaluate_booking_card` /
`evaluate_booking_chart`) — the same pattern the roster side already
follows. Current values below are from the currently active booking
upload (`backend/data/uploads/booking/v4.xlsx`, 2,961 rows, promoted
2026-07-26) and are shown only to make the rules concrete — see
"Data freshness" near the end of this document for the guarantee that
these numbers always reflect whichever version is active, on the very
next request after an upload or rollback.

All four filters on the page (Hours Type, Region/Market, Month/Week,
Department) narrow the same booking DataFrame via
`booking_metrics.get_filtered_records`, before any card or chart
computes — so every widget on this page reacts to every filter.

### Card: Total Employees — `49`
Distinct values of the **`Employee`** column on the booking sheet.

> Same label as the Total Employees card on HR Home, DIFFERENT
> definition: HR Home counts distinct `NEW_EMP_ID` over the whole
> roster (52), Utilization Home only sees employees who booked hours
> (49). The booking sheet is a subset of the roster by construction,
> so booking's Total Employees ≤ roster's Total Employees always.
> Declared as `total_employees_booking` in `cards:` so a diff between
> the two definitions is intentional and named, not accidental.
>
> **Cross-page relationship: a booking-only Employee is a WARNING, not
> an error.** A booking file can legitimately arrive before its
> matching roster refresh. `cross_dataset._unmatched_warning_check`
> surfaces every such Employee as a per-name warning on upload and the
> upload still commits — mirroring the "9 rows missing LWD" pattern on
> HR Analytics. Locked by
> `test_booking_only_employee_warns_but_does_not_block_upload`.

Real DAX measure name is `Total Employeess` (sic — typo preserved
verbatim from the exported Power BI model per the data-model skill).

### Card: Total Hours — `17,148.6`
Sum of the **`Employee Booked Hours`** column across every booking
row. Real DAX: `SUM('Sheet1'[Employee Booked Hours])`. Declared as
`total_hours` in `cards:` (`measure_type: sum`, `column_role:
hours_value`).

### Card: Client Hours — `11,431.0`
Sum of `Employee Booked Hours` narrowed to rows where
`Booked Hours Type` = "Client Hours". Declared as `client_hours`,
with `filter_column_role: hours_type` and `filter_label_key:
client_label` — the literal `"Client Hours"` lives in the `hours:`
block, so renaming it (e.g. "Billable Hours") is a one-line config
change.

### Card: Internal Hours — `5,717.6`
Mirror of Client Hours, narrowed to `Booked Hours Type` = "Internal
Hours". Guaranteed to satisfy `Client + Internal = Total` by the
`hours_split_covers_all_hours` invariant, which fires at upload time
if a third `Booked Hours Type` value ever appears (e.g. "Leave
Hours"). That invariant also serves as the arithmetic
`client_plus_internal_equals_total_hours` KPI-strip contract —
matching the exact shape of the roster's
`status_measures_partition_roster` (Active + Inactive + Strategic
Pool = Total).

### Card: Total Projects — `81`
Distinct values of the **`Project Name`** column, excluding blanks.

> **PROVISIONAL COLUMN RESOLUTION.** The real DAX measure targets
> `Sheet1[Project]`, but the source file has no column literally named
> `Project` — only `Project Name`. Resolved to `Project Name` as the
> only plausible match; if a real `Project` column later appears in
> the source, change the `project:` role in
> `configs/booking_metrics.yaml` and every reference follows.

### Chart: Weekly Hours Trend
Client Hours vs Internal Hours summed per **`Monday of Week`** — one
clustered bar per week, split by hours type. Declared as
`weekly_hours_trend` in `charts:` (`type: sum_by`, `group_column_role:
week_start`, `value_column_role: hours_value`, `split_column_role:
hours_type`). `split_column_role` was added specifically for this
chart — a `sum_by` with a split is a pivot over the split values.

Reconciles to the Total Hours card by construction: the
`weekly_trend_sums_to_total_hours` invariant asserts that every week's
(client + internal) hours summed equals the Total Hours KPI, with any
NaN-`Monday of Week` rows accounted for separately in the detail.

### Chart: Total Hours by Region / Market
Sum of hours grouped by `Region (EC)` and `Market (EC)`, rendered as
one bar per (region, market) pair with a combined "Region/Market"
label. Declared as `total_hours_by_region_market` in `charts:`
(`type: sum_by_hierarchical`, `primary_group_role: region`,
`secondary_group_role: market`, `value_column_role: hours_value`).
`sum_by_hierarchical` is a new chart type introduced specifically for
this shape — two group columns, one value column.

> **Renamed 2026-07-24** from the reference PDF's "Total Hours by
> Market(EC) and Region(EC)" to match METRICS.md house style (no
> source-column parentheticals). The Power BI original is what we're
> replacing; house style wins over verbatim fidelity.
>
> **UNCONFIRMED as a named Power BI measure.** No single DAX measure
> in the exported model combines `Region (EC)` and `Market (EC)` into
> one grouped total — this chart is a best-effort extension of the
> per-region total to also group by market, built to match the
> reference screenshot's combined-label behavior.

Reconciles to the Total Hours card by construction: the
`region_market_bars_sum_to_total_hours` invariant asserts every bar's
hours sum to Total Hours, with any rows carrying a blank
`Region (EC)` or `Market (EC)` accounted for separately in the
detail.

### Known data-quality note
Employees who booked hours must appear in the roster to be counted
in HR Home's Total Employees. Two exports arriving out of order —
booking before roster refresh — is expected and does NOT fail
validation: each booking-only Employee is a warning on the upload
report, and the upload still commits. This mirrors the "9 rows
missing LWD" pattern on HR Analytics: a data fix, not a code fix.

### Search / Results

The Search page (`/utilization/search`) is a **form only** — 7 filter
dropdowns (Month / Week, Region, Department, Entity, Holding, Hours
Type, Employee), no KPIs and no charts. Submitting it navigates to
`/utilization/results?...` with the selected values encoded as repeated
query parameters. Every one of those dropdowns is a `filters:` entry
in `configs/booking_metrics.yaml` (`applies_to_pages` includes
`utilization-search`), so the form's field set cannot drift from the
server's accepted parameter set.

> Previously the Search page had 6 filters, missing an Employee picker —
> users had to reach the Results page and scroll the paginated table to
> narrow to one person. The `employee` filter (booking-only, multi-select,
> options sourced from `booking.Employee` via
> `booking_metrics.get_filter_options`) closes that gap. Backend filter
> plumbing goes through the shared `_booking_filter_params` dep, so
> `/records` and every other utilization endpoint accept `?employee=...`
> without a per-route change.

> Previously the Results page had a right-side collapsible FiltersPanel
> duplicating the Search form's filters. Removed 2026-07-24 — the Search
> page owns filter selection and the Results page is now read-only for
> the current filter set (users click "Back to Search" to change it).
> The `FiltersPanel` component itself is kept in the codebase because
> Employee Utilization and Project Utilization drill-through pages still
> use it.

The Results page (`/utilization/results`) renders **5 KPI cards and a
paginated records table** over the booking sheet narrowed by the same
filter set. Every KPI is declared under `cards:` and computed through
`evaluate_booking_card`, so the values here and on Utilization Home
cannot compute the same label two different ways. The
`records_summary_reuses_declared_cards` invariant locks that in — one
declaration per KPI, one function per number.

Four of the five KPIs REUSE the Utilization Home declarations exactly:

| KPI | Reuses card | Definition |
|---|---|---|
| Total Hours | `total_hours` | see Page 7 above |
| Client Hours | `client_hours` | see Page 7 above |
| Internal Hours | `internal_hours` | see Page 7 above |
| Total Projects | `total_projects` | see Page 7 above |

The 5th KPI is Results-only:

#### Card: Average Hours — `5.87`
Mean of `Employee Booked Hours` across every booking row in the current
filtered slice. Declared as `average_hours` in `cards:` with a new
`measure_type: mean` — the fifth booking measure type, alongside
`distinct_count`, `sum`, and `count_rows`. Empty filtered set -> `0.0`
(the dispatcher guards against pandas' `NaN`-on-empty mean, matching
the Results endpoint's response-model contract that `average_hours` is
always a plain float).

> **UNCONFIRMED as a named Power BI measure.** No `Average Hours` DAX
> measure appears in the exported model — this KPI is a Search/Results
> summary-strip tile with no Power BI counterpart, kept because it
> gives the paginated records table a "hours-per-row" anchor that
> Total Hours divided by row count would otherwise force the frontend
> to compute client-side. Flagged PROVISIONAL alongside `total_projects`.

> Previously computed inline in `booking_metrics.get_records_summary`
> as `df["Employee Booked Hours"].mean()` — every other summary KPI
> already routed through the dispatcher, this one didn't. Now it does,
> and the routing is guarded by
> `records_summary_reuses_declared_cards`.

#### Records table
The paginated list of matching booking rows (S.No., Week Start, Date,
Employee, Project, Holding, Department, Team (EC), Region, Hours Type,
Hours). Row shape lives in `booking_metrics.records_to_dicts`; the
table's `total` field is the pre-pagination filtered row count, and
its footer's "Total" hours cell reads `summary.total_hours` directly
(no client-side aggregation), so the footer and the top-strip KPI
cannot disagree.

The leading `S.No.` column is a 1-based counter over the current
sorted/paginated position (`row.index + 1`), mirroring the Employee
Directory's `display: serial` convention. It has no backend field —
serial is a rendering concern, not stored data. Not YAML-declared
today because the Results table's column set isn't YAML-declared (unlike
`directory.columns`); a follow-up could introduce a `records.columns:`
block if the column set grows.

Filter sidebar semantics match Utilization Home's filter row: URL-driven,
propagates to every server request through the shared
`_booking_filter_params` FastAPI dependency — the same one Utilization
Home's summary/weekly-trend/region-market endpoints use. See
`docs/FILTERS.md` for the full filter semantics.

### Consistency rules (Search / Results additions)

| Invariant | Guarantees |
|---|---|
| `records_summary_reuses_declared_cards` | Results-page summary KPIs go through the same `evaluate_booking_card` declarations as Utilization Home — the two pages cannot compute the same label two different ways |

---

## Page filters — how the dropdowns work

Every filterable page (HR Home, HR Analytics, Workforce, Skills &
Experience, Employee Directory — Home has none) filters **server-side**:
the page sends the selected values to the `/roster` endpoints, which
re-run the YAML metric definitions over the narrowed rows. The filters
themselves are declared once, in the `filters:` block of
`configs/roster_metrics.yaml`, and used by both layers:

| Filter | Backed by | Notes |
|---|---|---|
| Status | `status` column | |
| Department | `designation` column | raw values — casing already canonicalised at ingestion |
| Region/Market | `region` column | |
| Skill | `primary_skill` column | raw values |
| Type | `employment_type` column | GCC / Non GCC |
| Allocation | `client` column | exact match on the raw client string (multi-client cells are one value, matching the naive `Clients Covered` count) |
| Grade | `grade` column | |
| Experience | *derived* from `workforce_by_experience_band` chart | reuses the chart's own band boundaries |
| Seniority Category | *derived* from `workforce_by_seniority_category` chart | reuses the chart's own buckets |

Design rules that keep filters honest:

- **One declaration, no drift.** The API reads *exactly* the filters
  declared in the config (`_filter_params` iterates `metric_config.filters()`),
  so adding a filter to the YAML makes the endpoints accept it and removing
  one stops it — the HTTP layer can never disagree with the config.
- **A shown dropdown is always sent.** The frontend converts filter state
  with one shared `buildServerFilters` helper, so a page can't display a
  dropdown without also passing it to the server (the bug that made
  Workforce's Grade and Skill dropdowns do nothing).
- **Dropdown values match the raw column.** Options are the raw distinct
  values the server compares against — never a re-normalised label, which
  would send a value the column never contains and silently return 0 rows.
- **Derived filters reuse chart bucketing.** Experience and Seniority
  Category filter by the *same* band logic the matching chart draws, so a
  band and its chart can never disagree about where a boundary is.

Enforced by `tests/test_roster_filters.py`: every option of every filter
must narrow to only matching rows, single-value filters must partition the
whole roster, and each declared filter must work end-to-end over HTTP.

## Consistency rules we enforce automatically

Checked by `metric_invariants.py` — in the test suite *and* on every
upload, so a file that would make the dashboard contradict itself is
flagged before it goes live:

| Invariant | Guarantees |
|---|---|
| `strategic_pool_same_everywhere` | Strategic Pool is the same number on every page that shows it |
| `closing_headcount_is_present_workforce` | Closing Headcount = Active + Strategic Pool |
| `status_measures_partition_roster` | Active + Inactive + Strategic Pool = Total Employees |
| `category_split_matches_status` | Home's Workforce Category agrees with HR Home's Status Split |
| `seniority_split_covers_present_workforce` | The seniority donut covers exactly the current workforce |
| `charts_account_for_everyone` | Every breakdown chart totals to the population it describes — blanks counted, never dropped |
| `every_status_has_a_workforce_meaning` | No status is left without a decision on whether it counts as present |
| `exits_equals_inactive` | Exits and Inactive stay the same number — they are the same people |
| `every_exit_has_a_leaving_date` | Every exit has an `LWD`, so the monthly leavers trend can account for all of them |
| `hours_split_covers_all_hours` | Client + Internal = total booked hours, so no hours category is silently missing from the donut (also serves as `client_plus_internal_equals_total_hours` — same arithmetic, one check) |
| `weekly_trend_sums_to_total_hours` | Utilization Home's Weekly Hours Trend, summed across every week, equals Total Hours (any unplaced NaN-week rows are named in the detail) |
| `region_market_bars_sum_to_total_hours` | Utilization Home's Total Hours by Region / Market bars sum to Total Hours (any rows with a blank Region or Market are named in the detail) |
| `records_summary_reuses_declared_cards` | Utilization Results' 5 summary KPIs route through the same declared cards as Utilization Home — same label, same declaration, no page-to-page drift |
| `overview_client_hours_equals_booking_client_hours` | Overview's Formula A numerator (per-employee client-hour sum) reconciles to Utilization Home's Client Hours — the ground-truth-to-booking runtime switch cannot have wired a different underlying column |
| `employee_utilization_totals_reconcile` | For every Employee, the drill-through Total Hours KPI equals that employee's summed `Employee Booked Hours` — same rows, same reduction |
| `project_utilization_totals_reconcile` | Same shape, scoped by Holding — the Project drill-through Total Hours reconciles to the holding's summed booking rows |
| `overview_average_period_utilization_pct_in_range` | Formula A ratios are bounded to [0, 1] by construction, so their mean is too — a value outside means a booking row has a negative/out-of-range hours cell or a new Booked Hours Type category has broken the denominator |

Each one exists because of a real failure, not a hypothetical: the
Strategic Pool 1-vs-3 split across two pages, the Closing Headcount
47-vs-38 contradiction on a single page, and bars that totalled less than
the card above them because blanks were dropped.

---

## Page 8 — Utilization Overview

The dashboard's utilization landing page: 3 KPIs plus a weekly trend, a
utilization-band split, and a per-employee ranking. As of 2026-07-26
**every value on this page is computed from the booking sheet** using
Formula A — the ground-truth `Utilization_Long` sheet is no longer a
runtime input. See `configs/booking_metrics.yaml` for the declarations
(cards + charts) and `services/utilization_metrics.py::get_utilization_overview`
for the orchestration.

### Ground truth is QA-only

`PowerBI_Ready_Utilization_May_2026.xlsx` used to power this page
directly, but the file is:
1. A rounded export of an underlying DAX calculation — Formula A
   reproduces the same numbers exactly for 147/156 (94.2%) of matched
   employee/weeks, and to within 0.3-0.4 pp for the remaining 9 rows
   (see `utilization_metrics.py`'s module docstring). Its `Weekly
   Utilization %` column is therefore a *view* of Formula A, not an
   independent source of truth.
2. Snapshot-only: it covers **4 weeks** (2026-05-04 to 2026-05-25) while
   the booking sheet spans 7+ weeks. Consuming it at runtime meant the
   Overview page silently trailed the current data by whatever the
   ground-truth's own refresh cadence was — and it was hand-cut in Excel.
3. Optional at deployment time: a fresh clone with no ground-truth file
   present would refuse to serve `/utilization/overview` and produced a
   500. Moving Overview to the booking sheet removes that dependency;
   the app now boots and answers /overview cleanly with no ground-truth
   file present, and the QA path returns a helpful 404 (see
   Consistency Rules below).

The file survives as an OPTIONAL QA input. The admin-only endpoint
`GET /api/v1/qa/reconcile?dataset=utilization` reads it lazily and
returns the full Formula A vs ground-truth reconciliation — the same
`reconcile_weekly_utilization` function used by the module's regression
test. This is where the 9/156 residual mismatches surface today (before
the switch they weren't surfaced anywhere — the runtime just showed the
ground-truth's shipped values). Not a data-quality regression: it is the
opposite, an unblocked observability.

### Formula A — the one measure that matters here

For each (`Employee`, `Monday of Week`) on the booking sheet:

```
Weekly Utilization % = Client Hours / (Client Hours + Internal Hours)
```

where `Client Hours` and `Internal Hours` are the SAME sums the
Utilization Home KPI strip already reports (via the `client_hours` and
`internal_hours` cards). The invariant
`overview_client_hours_equals_booking_client_hours` locks that
identity: Overview cannot silently read a different underlying column
from Utilization Home.

Two things Formula A DOES NOT do, both deliberately:
- **No fixed 45hr denominator.** Formula B (`Client Hours / 45`) is
  ruled out — 124/156 exact matches vs Formula A's 147/156. The
  denominator is that employee's actual logged total for that week,
  which is what "utilization" means when someone with a 2-day timesheet
  should still round-trip to 100%.
- **NaN, not 0%, on an empty week.** An employee/week with zero logged
  hours yields undefined utilization, not "0% utilized" — a different
  fact from "worked 0 client hours out of some logged total". Preserved
  through the pipeline (dropped from ranking, excluded from means).

#### Worked example (real employee, v4 active data, 2026-07-26)

`Kartik Dhiwar` across the full booking period: `Client Hours = 319.0`,
`Internal Hours = 59.0` (from `/api/v1/utilization/employees/Kartik Dhiwar`).

```
period_util_pct[Kartik Dhiwar] = 319.0 / (319.0 + 59.0)
                                = 319.0 / 378.0
                                = 0.843915...  (84.39%)
```

This exact figure — `0.843915343915344` — is what the Overview
`employee_ranking` array reports for this employee, and is exactly
reproduced by `test_overview_formula_a_reconciles` in
`backend/tests/test_utilization_manual_reconciliation.py`, which
independently recomputes every employee's `period_util_pct` with plain
pandas groupby/sum and asserts it against the live endpoint. For the
per-week form (Weekly Utilization Trend), the same employee's week of
`2026-05-04` is `40.0 / (40.0 + 5.0) = 0.8888...` (88.9%) — a single
row of the `hours_by_week` breakdown, not aggregated with any other week.

### Aggregate-then-ratio: what "period" means

The Overview headline KPI is `Average Period Utilization %`, defined as:

```
period_util_pct[e] = Σ Client Hours over the period, for e
                   / Σ (Client + Internal) over the period, for e
Average Period Utilization % = mean(period_util_pct)
```

**Aggregate-then-ratio per employee, then mean across employees.** This
is decision D1a (2026-07-26). The alternative — mean of per-week ratios
— would weight a 2-hour partial week the same as a 40-hour full week;
the aggregate-then-ratio form gives every logged hour equal weight and
matches what "period total" reads as literally. It also matches the
ground truth's `Period Total Utilization %` column's semantics, per the
147/156 exact-match reconciliation.

Every KPI + chart on this page routes through the same YAML declaration
so the values cannot compute two different ways. The wiring:

| Widget | Card / chart declaration | measure_type / type |
|---|---|---|
| Average Period Utilization % | `average_period_utilization_pct` | `avg_of_chart` on `employee_period_utilization` |
| Total Employees | `total_employees_booking` (reused from Utilization Home) | `distinct_count` |
| Latest Week Utilization % | `latest_week_utilization_pct` | `avg_of_chart` on `employee_period_utilization`, `scope_to_latest_of_role: week_start` |
| Weekly Utilization Trend | `weekly_utilization_trend` | `avg_of_group_ratios` (outer: week_start, inner: employee) |
| Utilization Split | `utilization_split` | `ratio_bands` over `employee_period_utilization` |
| Employee Period Utilization % (ranking) | `employee_period_utilization` | `ratio_by` (group: employee) |

Three new engine primitives were added to support this page and are
deliberately generic:
- `measure_type: ratio` — a scalar `sum(num)/sum(denom)`, each side
  optionally filtered against an hours-block label key.
- `measure_type: avg_of_chart` — mean over the values of a declared
  chart's output. Optional `scope_to_latest_of_role` pre-narrows the
  frame to rows whose role-column value equals its max.
- `chart type: ratio_by` — per-group aggregate-then-ratio. `aggregate:
  per_group` means `sum(num)/sum(denom)` within each group.
- `chart type: ratio_bands` — first-match-wins band counts over a
  `ratio_by` chart's values, same `below` semantics as `numeric_bands`.
- `chart type: avg_of_group_ratios` — for each outer_group value,
  compute per-inner-group ratios and return the mean. Backs the Weekly
  Utilization Trend under D1a's per-employee-first semantics.

Numbers change from the previous ground-truth-sourced page:

| | Ground-truth sourced (before) | Booking-derived (now) |
|---|---|---|
| Total Employees | 41 | 46+ (booking-only employees now included) |
| Weeks in trend | 4 (May only) | 7+ (full booking range) |
| Formula body | DAX calculated column | Formula A, direct compute |
| Reconcile residuals | Hidden in the shipped column | Visible only via `/qa/reconcile` |

### Card: Average Period Utilization %
Mean of per-employee period ratios (formula above). Routed via
`evaluate_booking_card` on `average_period_utilization_pct`, which
composes `evaluate_booking_chart(employee_period_utilization).values()`
and takes the mean.

### Card: Total Employees
Distinct booking-sheet `Employee` values — same declaration as
Utilization Home (`total_employees_booking`), same `distinct_count`
primitive, so the two pages cannot report different Overview vs
Utilization Home headcounts. The DIFFERS-from-roster relationship (46
booking vs 52 roster) is unchanged from Page 7.

### Card: Latest Week Utilization %
Mean of per-employee ratios in the latest `Monday of Week`. Declared as
`latest_week_utilization_pct` with `scope_to_latest_of_role: week_start`
— the dispatcher narrows the frame to that week before running
`employee_period_utilization` and averaging. On a booking snapshot that
only has one week of data, this equals `Average Period Utilization %` by
construction.

### Chart: Weekly Utilization Trend
One point per `Monday of Week` — the **mean of per-employee Formula A
ratios in that week**. For each employee active in the week, compute
`Client Hours / (Client Hours + Internal Hours)` for that (employee,
week); then mean those ratios across employees. Same D1a semantics as
the headline KPIs applied at week granularity, so the latest week's
trend value equals `Latest Week Utilization %` by construction.

Declared as `weekly_utilization_trend` (chart type `avg_of_group_ratios`,
`outer_group_role: week_start`, `inner_group_role: employee`) — a new
chart type added specifically to keep the "per-employee-first, then
mean" semantics consistent across the KPI strip and the chart. An
alternative aggregate-then-ratio at the whole-week level was tried and
rejected: it would weight a heavy logger the same as a light logger and
drift 0.5-3pp from the KPIs each week.

Edge cases confirmed on the current booking snapshot:
- **100% weeks** — one employee active in that week logging only Client
  Hours (e.g. 2026-04-20). The mean of a single 1.0 ratio is 1.0.
- **0% weeks** — every active employee in that week logged only
  Internal Hours (e.g. 2026-04-27 with 26 employees, all
  `Booked Hours Type == "Internal Hours"`). The mean of 26 zeros is 0.

Both are correct D1a values; the shape is a data pattern (early / low
utilization periods), not a metric bug.

### Chart: Utilization Split
Band counts over the per-employee ratios: `high` (>= 0.90), `moderate`
(0.80 to < 0.90), `low` (< 0.80). Declared as `utilization_split`
(`ratio_bands`, source: `employee_period_utilization`).

> **Thresholds are PROVISIONAL.** The bands ≥0.90 / ≥0.80 / else are
> the same green / amber cues documented in the ground-truth sheet but
> have not been confirmed against a real DAX `Utilization Band` measure
> (still missing per data-model SKILL.md's "Flagged discrepancies"
> section). They now also share the caveat that the underlying values
> are booking-derived Formula A rather than the ground-truth's shipped
> ratios — most rows still land in the same band because Formula A and
> ground truth agree on 147/156 rows, but a boundary case may drift.
> Adjust in `charts.utilization_split.bands` — one-line YAML change.

### Chart: Employee Period Utilization %
Per-employee period ratio (aggregate-then-ratio), sorted descending.
Declared as `employee_period_utilization` (`ratio_by`, `group_column_role:
employee`). Populates the same underlying data both the ranking chart
and the Utilization Split donut read from, so a boundary case cannot
land in one but not the other.

### Consistency rules (Overview additions)

| Invariant | Guarantees |
|---|---|
| `overview_client_hours_equals_booking_client_hours` | Overview's Formula A numerator = Utilization Home's Client Hours (same physical column, same reduction) |
| `overview_average_period_utilization_pct_in_range` | The headline KPI stays in [0, 1] — a value outside means a negative hours cell or a broken denominator, named in the detail |

---

## Page 9 — Employee Utilization drill-through

Reached from the sidebar (`/utilization/employees`) or from a click in
Utilization Search / Results. Two states:

- No employee selected — a picker table: one row per Employee with
  totals (aggregated client-side over the paginated records feed).
  Same shape as the Project picker, no server-side ranking of employees.
- One employee selected (`/utilization/employees/{name}`) — 4 KPIs, 2
  charts, 3 page-local filters.

### The intentional scope split — KPIs vs charts

The four KPIs describe the WHOLE employee: page-local filters (Hours
Type, Project, Week) narrow **only the two charts**, not the KPI strip.
This is deliberate and now visible in the YAML declaration:
`filter_scope: whole_scope` on every drill-through KPI card. The
`evaluate_booking_card` dispatcher itself never filters — the ENDPOINT
decides which frame to hand in — but the declaration explains the choice
so a future reader isn't puzzled by the KPIs "ignoring" the filter row.

Two `filter_scope` values today:
- `whole_scope` — every drill-through KPI, plus Overview's KPIs.
- `filtered` — Utilization Home + Search / Results KPIs (endpoint
  pre-narrows the frame).

### Card: Total Hours
Sum of `Employee Booked Hours` across every booking row for this
Employee. Reuses the `total_hours` declaration from Utilization Home —
same measure_type: sum, same column role — so the drill-through and the
KPI strip on Home cannot compute Total Hours two different ways.

### Card: Client Hours
Same reuse: sum of `Employee Booked Hours` narrowed to `Booked Hours
Type == "Client Hours"`, from the `client_hours` card.

### Card: Internal Hours
Mirror of Client Hours, from the `internal_hours` card. `Client +
Internal = Total` holds by the same `hours_split_covers_all_hours`
invariant that guards it on Utilization Home.

### Card: Total Projects
Distinct `Project Name` for this employee, from the `total_projects`
card. Same PROVISIONAL-column-resolution caveat as Page 7 (the DAX
targets `Sheet1[Project]`, resolved to `Project Name`).

### Chart: Total Hours by Project
Sum of `Employee Booked Hours` per `Project Name`, desc. Declared as
`employee_hours_by_project` in `charts:` (`sum_by`, `group_column_role:
project`, `value_column_role: hours_value`). Routes through
`evaluate_booking_chart` so a shape change is a YAML edit.

### Chart: Total Hours by Week Start
Per-week bucket of `Employee Booked Hours`, split by `Booked Hours
Type` — Client / Internal columns per week, one bar cluster per week.
Declared as `employee_hours_by_week` (`sum_by_split`, group: week_start,
split: hours_type). `sum_by_split` is a new chart type that returns
the projected `list[{group, split_1: v, split_2: v, ...}]` shape rather
than a raw pivot — so the endpoint doesn't need a per-chart Python
reshape (this was a real duplication between the two drill-throughs).

### Records table
Not a chart, not a KPI — a page-local projection built client-side from
`/utilization/records?employee={name}`. Reuses the Utilization Results
page's records column set. The 258-row booking sheet is small enough
to fetch in full and filter client-side; scaling that to a larger
dataset would move filtering server-side, and the `employee` filter
parameter is already accepted by `/utilization/records`.

### Page filters
Three: Hours Type (dropdown from `hours_type` filter YAML), Project (a
page-local option list — this employee's distinct project set, not a
global filter), Week (hierarchical, reuses the `week` filter YAML).
Filter LABELS are read from `useFilterConfig` on the frontend — no
hardcoded English strings on the page.

---

## Page 10 — Project (Holding) Utilization drill-through

Reached from the sidebar (`/utilization/projects`) or a click on a
Holding row in Search / Results. Same shape as the Employee page: a
picker for the param-less state, and a detail page for a selected
`/utilization/projects/{holding}`.

### Cards
Total Employees, Total Hours, Client Hours, Internal Hours — all four
`filter_scope: whole_scope`, describing the entire holding regardless
of the page's Employee filter (which narrows only the charts + detail
table).

- **Total Employees** — distinct booking-sheet `Employee` values for
  this holding. Derived client-side from the paginated records feed
  today (matches the Employee-picker pattern); a follow-up could
  declare a `total_employees_for_holding` card, but the value is a
  straightforward count over a small frame and hasn't been split out.
- **Total Hours / Client Hours / Internal Hours** — reuse the same
  declarations as Utilization Home and the Employee page. One
  declaration, three surfaces, no drift.

### Chart: Total Hours by Employee and Hours Type
Sum of `Employee Booked Hours` per (Employee, Booked Hours Type). One
bar per employee, split Client / Internal. Declared as
`project_hours_by_employee` (`sum_by_split`, group: employee, split:
hours_type).

### Chart: Total Hours by Week Start and Hours Type
Same shape as the Employee page's week chart, holding-scoped. Declared
as `project_hours_by_week` (`sum_by_split`, group: week_start, split:
hours_type).

### Detail table (Employee, Project, Region, Department)
A distinct-tuple projection over this holding's rows —
`drop_duplicates(["Employee", "Project Name", "Region (EC)",
"Department"])`. Not YAML-declared. Kept in code because it is a
PROJECTION, not an aggregation — there is no number to reconcile, only
rows to display. Adding a `distinct_rows` chart type would only add
indirection for zero engine gain. Same principle as the Records table's
row shape on Page 7's Results.

### Page filter
One: Employee (page-local, distinct set of this holding's employees).
Same treatment as Project on the Employee page — a page-local option
list, not a global filter YAML entry.

### Consistency rules (drill-through additions)

| Invariant | Guarantees |
|---|---|
| `employee_utilization_totals_reconcile` | Every Employee's drill-through Total Hours equals that employee's summed booking rows — sampled across 5 employees per run |
| `project_utilization_totals_reconcile` | Every Holding's drill-through Total Hours equals that holding's summed booking rows — sampled across 5 holdings per run |

---

## Known data-quality note

9 employees are marked `Inactive` but have **no `LWD`** (last working
day). This no longer affects headcount, but it does mean they are not
counted as **Exits**, so Exits (5) is lower than Inactive (14) and
attrition is understated. Filling in `LWD` for those rows would resolve
it — a data fix, not a code change. *(Exits/attrition appear on HR
Analytics, not Home — to be reviewed when we get to that page.)*

---

## Data freshness — how uploads take effect

Uploading a new file OR rolling back to a prior version must make
**every** dashboard consumer of that dataset (every card, chart, filter
dropdown, and drill-through) reflect the newly active version on the
very next request — no stale reads, for both `roster` and `booking`
(and, for completeness, `ground_truth`, even though it is QA-only —
see above).

**Backend guarantee.** `backend/app/services/data_loader.py` holds one
module-level in-memory cache per dataset:

| Cache variable | Populated by | Invalidated by |
|---|---|---|
| `_roster_cache` | `get_roster_df()` | `reload_roster()` |
| `_booking_cache` | `get_booking_df()` | `reload_booking_data()` |
| `_booking_prepared_cache` | `get_booking_df_prepared()` | `reload_booking_data()` (sets it to `None`; recomputed lazily from the fresh `_booking_cache` on next read — see `data_loader.py` line ~76) |
| `_utilization_ground_truth_cache` | `get_utilization_ground_truth_df()` | `reload_utilization_ground_truth()` |

Both `process_upload()` and `rollback()` in
`backend/app/services/validation/service.py` call a single shared
`_reload_active(file_type)` helper (lines ~41-49) immediately after the
new version is promoted or the active pointer is moved back, mapping
`file_type` to the correct `reload_*` function:

```python
{
    "roster": data_loader.reload_roster,
    "booking": data_loader.reload_booking_data,
    "ground_truth": data_loader.reload_utilization_ground_truth,
}[file_type]()
```

Because upload and rollback share this one call site, there is no way
for one code path to refresh the cache while the other forgets to —
a class of bug (rollback endpoint missing a reload call, or reloading
only part of a cache set) that this design rules out structurally
rather than by convention. `reload_booking_data()` refreshes both
`_booking_cache` and `_booking_prepared_cache` together (clearing the
latter) specifically because the prepared frame is derived from the
raw one; refreshing only the raw cache would leave every utilization
page — which reads the prepared frame — on stale prepared data even
though `_booking_cache` itself was current.

Locked in by `backend/tests/test_upload_filter_reflection.py`: upload
version A, assert `/utilization/filter-options` and
`/utilization/overview` (plus roster equivalents) reflect A; upload
version B, assert both endpoints now reflect B and not A; roll back to
A, assert immediate reflection of A again — for both `roster` and
`booking`.

**Frontend guarantee.** `frontend/src/lib/data-admin-api.ts`'s
`useUploadDataset()` / `useRollbackDataset()` mutations call
`invalidateDashboardCachesFor(qc, fileType)` on success, which
invalidates every TanStack Query cache key that reads the affected
dataset — not just the admin page's own `['data-admin', ...]` status
queries (which is all the mutations invalidated previously, leaving
every other page's cached response stale until an unrelated refetch or
a manual reload happened to occur):

| `file_type` | Query keys invalidated |
|---|---|
| `roster` | `['roster']`, `['booking']` (Home's utilization donut also reads booking-derived summary), `['config', 'filters', 'roster']` |
| `booking` | `['booking']`, `['utilization']` (every Utilization page), `['config', 'filters', 'booking']` |
| `ground_truth` | none — only consumed by the admin-only `/qa/reconcile` endpoint, which is not cached via TanStack Query |

**Net guarantee:** after any successful upload or rollback response,
the next request to any endpoint or any page re-reads the active
version — verified end-to-end (backend cache + live HTTP response) by
`test_upload_filter_reflection.py`, and the specific "stale picker
showing an old version's project/holding counts" symptom this section
exists to prevent is exactly what that test's filter-options assertions
guard.
