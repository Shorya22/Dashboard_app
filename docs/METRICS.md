# Dashboard Metrics — how every number is calculated

How each card and chart gets its number, in plain terms. Written page by
page as we verify them; anything not listed here has not been reviewed yet.

**Progress**

| Page | Status |
|---|---|
| Home | ✅ 3 cards + 4 charts (Closing Headcount is a date measure — see below) |
| HR Home (HR Portal) | ✅ all 4 cards + 4 charts verified |
| HR Analytics | ✅ 5 cards + 4 charts (Attrition % is a formula — see below) |
| Workforce | ⬜ not reviewed |
| Skills & Experience | ⬜ not reviewed |
| Employee Directory | ⬜ not reviewed |
| Utilization pages | ⬜ not reviewed |

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
| **Closing Headcount** | A date-window measure ("joined by the period end and still here"). Which column is the joining date and which statuses count as here are config; walking the calendar is an algorithm. |

Everything else on Home, HR Home and HR Analytics — 24 of 26 cards and
charts — is declared in YAML.

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
| Ground truth | `PowerBI_Ready_Utilization_May_2026.xlsx` | Utilization Overview page |

The dashboard always reads the **latest promoted upload**; if nothing has
been uploaded it falls back to the bundled file.

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
| `hours_split_covers_all_hours` | Client + Internal = total booked hours, so no hours category is silently missing from the donut |

Each one exists because of a real failure, not a hypothetical: the
Strategic Pool 1-vs-3 split across two pages, the Closing Headcount
47-vs-38 contradiction on a single page, and bars that totalled less than
the card above them because blanks were dropped.

---

## Known data-quality note

9 employees are marked `Inactive` but have **no `LWD`** (last working
day). This no longer affects headcount, but it does mean they are not
counted as **Exits**, so Exits (5) is lower than Inactive (14) and
attrition is understated. Filling in `LWD` for those rows would resolve
it — a data fix, not a code change. *(Exits/attrition appear on HR
Analytics, not Home — to be reviewed when we get to that page.)*
