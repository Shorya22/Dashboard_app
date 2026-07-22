# Dashboard Metrics — how every number is calculated

How each card and chart gets its number, in plain terms. Written page by
page as we verify them; anything not listed here has not been reviewed yet.

**Rule we follow:** one business concept = one definition, in one place.
If the same label appears on two pages it must resolve to the same
function, never be recomputed separately. That is what caused the
"Strategic Pool showed 1 on Home and 3 on HR Home" bug.

**Where the rules live:**

| What | Where | Who can change it |
|---|---|---|
| What a valid upload looks like (columns, types) | `backend/app/services/validation/configs/*.yaml` | Config edit, no code |
| What the values *mean* (which status counts as present, seniority keywords) | `backend/app/services/configs/roster_metrics.yaml` | Config edit, no code |
| Date-window logic (joiners, exits, attrition) | `backend/app/services/roster_metrics.py` | Developer |

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

## Consistency rules we enforce automatically

Checked by `metric_invariants.py` — in the test suite *and* on every
upload, so a file that would make the dashboard contradict itself is
flagged before it goes live:

1. Strategic Pool is the same number everywhere it appears.
2. Closing Headcount = Active + Strategic Pool.
3. The Workforce-by-Seniority split covers exactly the present workforce.
4. The Status breakdown accounts for every employee (no status silently
   uncounted).
5. Active + Inactive + Strategic Pool = Total Employees.
6. Client Hours + Internal Hours = total booked hours (no hours category
   silently excluded from the donut).

---

## Known data-quality note

9 employees are marked `Inactive` but have **no `LWD`** (last working
day). This no longer affects headcount, but it does mean they are not
counted as **Exits**, so Exits (5) is lower than Inactive (14) and
attrition is understated. Filling in `LWD` for those rows would resolve
it — a data fix, not a code change. *(Exits/attrition appear on HR
Analytics, not Home — to be reviewed when we get to that page.)*
