---
name: data-model
description: Use whenever reading, cleaning, aggregating, or writing any endpoint/query against the employee/workforce Excel data — headcount, attrition, deployment, experience, or grade metrics. This is the ground-truth schema and known data-quality issues for this dataset. Read before writing any pandas/SQL logic that touches this data.
---

# Workforce data model

This dataset is an **employee roster / staffing dashboard** — headcount,
deployment, tenure, and attrition tracking. It is not sales/financial
data. All metric logic must be built against the actual columns below,
not assumed generic dashboard metrics.

## Column dictionary

| Column | Meaning | Notes / gotchas |
|---|---|---|
| `EMP ID` | Legacy employee ID | Mixed formats (e.g. `D6203`, `44034`) — treat as string, never cast to int |
| `NEW_EMP_ID` | Current employee ID | Use this as the primary key, not `EMP ID` |
| `NAME` | Full name | Free text, inconsistent spacing (double spaces between first/last name in source data) — trim whitespace before display or grouping |
| `GRADE` | Internal grade level | Values like `G3A`, `G4`...`G8` — sort order is NOT alphabetical (`G3A` < `G4`), define an explicit ordinal mapping if grade needs to be sorted or charted. **UPDATE (2026-07-15):** the file also now contains a `Grade TBD` value (a new, not-previously-documented marker, analogous to `Client TBD`/`PM TBD`/`Seniority TBD` elsewhere) — no code currently hardcodes a GRADE ordinal list, so nothing needed a fix, but any future ordinal mapping must include an explicit `Grade TBD` slot (or filter it out and flag rather than let it sort implicitly) |
| `DEPUTATION` | Onshore/offshore | Currently all sample rows are `OFFSHORE` — confirm other values exist before hardcoding a filter |
| `WORK_LOCATION` | Physical office | e.g. `PUNE 3` |
| `SUPERVISOR (Hexaware)` | Direct manager name | Free text, same name-spacing issue as `NAME` |
| `DOJ (Hexaware)` | Date joined Hexaware | Date, format `DD-Mon-YY` |
| `DOJ (DEPT)` | Date joined current department/project | Can be later than `DOJ (Hexaware)` — this is an internal transfer date, not a new hire date |
| `Today` | Snapshot date the export was taken | Same value across all rows in one export — use this as "as of" date for tenure calculations, not the system's current date, so historical exports still compute correctly |
| `Hexaware Experience (Years)` | Tenure at this company | Decimal years |
| `Before Hexaware Experience` | Prior experience elsewhere | Decimal years |
| `Total Experience` | Sum of the two experience columns | **Derived field — validate it always equals `Hexaware Experience + Before Hexaware Experience`; flag any row where it doesn't** |
| `Primary Skill` | Core technical skill | e.g. `iOS`, `Salesforce`, `Drupal` |
| `Working Entity` | Business unit code | e.g. `DTNL`, `DTIE`, `AMER`, or `Hexaware` for internal/corporate staff |
| `Region` | Geography | `EMEA`, `AMER`, or `Hexaware` (internal) |
| `Market` | Sub-region/market | e.g. `BENO`, `UKI`, `DACH`, `AMER` |
| `Client as on June 2026` | Current client(s) | **Can contain multiple clients in one cell**, comma-separated (e.g. `"Managed Services, Scandlines, Inter Milan and Blackroll"`). `"Client TBD"` means unallocated/bench. See multi-value handling below. |
| `Project Manager` | PM name(s) | **Also multi-value**, and the delimiter/order does not reliably align 1:1 with the Client column's entries — do not assume positional mapping between the two without explicit confirmation. `"PM TBD"` pairs with `"Client TBD"`. |
| `Skill` | Skill category/practice | Broader grouping than `Primary Skill` (e.g. `Front End`, `QA`, `Mobile`) — check whether this should be the axis for skill-based charts instead of `Primary Skill` |
| `Designation` | Job title | Free text |
| `Seniorirty Level` | Seniority band | **Column name has a typo in the source file ("Seniorirty") — keep the exact source spelling when reading the file, rename to `seniority_level` only in the cleaned/output layer** |
| `Type` | GCC vs Non GCC | Binary category, used for org-structure splits |
| `LWD` | Last working day | Only populated when `Status = Inactive` |
| `Reason for Leaving` | Attrition reason | e.g. `Involuntary` — only populated when `Status = Inactive`; empty for active employees is expected, not missing data |
| `Status` | Active / Inactive | Primary filter for headcount vs attrition metrics |
| `Declaration Signed` | Compliance flag | `Yes`/`No` — likely a compliance-tracking metric, not a performance one |
| `DEPT ID` | Work email | Format `firstname.lastname@company.com` — do not treat as a unique ID with the same guarantees as `NEW_EMP_ID` (naming collisions possible) |

## RESOLVED (2026-07-16): `DOJ (DEPT) = "TBD"` (2 rows) — was a DAX BLANK() semantics bug, not a data gap

Two active employees have the literal string `"TBD"` in `DOJ (DEPT)` instead
of a date: `Rahul Malhotra` (`NEW_EMP_ID 2000194634`, `DOJ (Hexaware)
14-May-26`) and `Shorya Sharma` (`NEW_EMP_ID 2000195658`, `DOJ (Hexaware)
22-Jun-26`). Both have a valid `DOJ (Hexaware)` — this looks like a recent
department-transfer date that was simply never recorded.

**This was previously (incorrectly) documented as "DAX-faithful behavior,
not a bug." It was in fact a real DAX-to-pandas translation bug**, found
and fixed 2026-07-16:

- In real DAX, `BLANK()` inside a numeric/date comparison behaves like the
  value `0` (effectively epoch-zero, `1899-12-30`). So
  `BLANK() <= EndDate` evaluates `TRUE`, `BLANK() >= StartDate` evaluates
  `FALSE` (any real `StartDate` is after epoch-zero), and
  `ISBLANK(BLANK())` evaluates `TRUE`.
- pandas' `NaT` (what `"TBD"` parses to via `pd.to_datetime(...,
  errors="coerce")`) compares `False` against **every** operator
  direction — this is NOT equivalent to DAX's `BLANK()` semantics. The
  old code relied on this NaT-always-False behavior for both `<=` and
  `>=` comparisons, which happened to accidentally match DAX for the
  `>=` direction (`Joiners`) but silently diverged for the `<=` direction
  (`Closing Headcount`, `Opening Headcount`) and for `ISBLANK()`
  (`Strategic Pool`, which checked the raw string column instead of the
  parsed date column and so never saw a "blank" at all).

**Fix**, in `backend/app/services/roster_metrics.py`:
- `get_strategic_pool`: now checks `_parse_dept_dates(df).isna()` (the
  parsed/coerced date column) instead of `df["DOJ (DEPT)"].isna()` (the
  raw string column) — "TBD" parses to `NaT`, which is the correct
  pandas analogue of a Date-typed Power BI column importing an
  unparseable value as `BLANK()`. Now returns **2** (was 0).
- `get_closing_headcount` / `get_opening_headcount`: the `DOJ (DEPT) <=
  EndDate` (or `<= PreviousDate`) filter is now explicitly
  `doj.isna() | (doj <= end)`, encoding blank-as-always-satisfies-`<=`
  intentionally rather than relying on NaT's (wrong) default-False
  behavior. `Closing Headcount` (full range) is now **47** (was 45);
  Jun 2026 explicit-period Closing Headcount is also **47** (was 45).
- `get_joiners`: the `DOJ (DEPT) >= StartDate` filter is now explicit
  (`doj.notna() & (doj >= start) & (doj <= end)`) for the same reason,
  even though the resulting value is unchanged (**50**, full range) —
  this direction happened to already match DAX under NaT's default
  behavior, but was accidental, not intentional, prior to this fix.

**New values** (real roster file, full date range unless noted):
`Strategic Pool = 2`, `Closing Headcount = 47`, `Opening Headcount = 2`
(full range — a genuinely new consequence: blank DOJ is always `<=` any
date including `PreviousDate`, so both TBD rows also newly satisfy
`Opening Headcount`'s full-range filter), `Joiners = 50` (unchanged),
`Attrition % = 9.6154%` (was 10.0%, now matches the Power BI reference
PDF's ~9.6% almost exactly). All locked in as regression tests in
`backend/tests/test_roster_metrics.py` and
`backend/tests/test_roster_breakdowns.py`.

No HR/business-owner input was needed — this required no data change, only
a code fix to correctly translate DAX's `BLANK()` semantics into pandas.

## RESOLVED (2026-07-16): `Departments` = 30 vs reference 29 — casing-duplicate `Designation` value

A naive `DISTINCTCOUNT('HR MASTER'[Designation ])` on the real roster file
returns **30**, one more than the reference model's **29**. Root cause:
`"SalesForce Core Developer"` (2 rows) and `"Salesforce Core Developer"`
(2 rows) are the same job title differing only in the capital "F" in
"Salesforce" — a genuine casing-duplicate data-quality issue in
`Designation`, identical in nature to the already-fixed `Seniorirty
Level` casing duplicates (`"Premium Lead"` vs `"Premium lead"`,
`"Standard Senior"` vs `"Standard senior"`).

**Decision (confirmed by the business owner):** apply the same
normalize-to-title-case-before-counting treatment used for `Seniorirty
Level` (see `_normalize_seniority_label` in
`backend/app/services/roster_metrics.py`). A new
`_normalize_designation_label` helper (thin wrapper around
`_normalize_seniority_label`) is used by `get_departments()` to
normalize `Designation` before calling `nunique()`. `get_departments()`
now correctly returns **29**, matching the reference. This is a genuine
data-quality fix, not an arbitrary number-matching hack — it happens to
also bring the count in line with the reference, which further
validates the fix.

The underlying casing inconsistency is not silently absorbed: it's
surfaced as a new `designation_casing_mismatch` warning in
`get_data_quality_warnings()`, following the exact same pattern as the
existing `seniority_level_casing_mismatch` warning. Regression tests:
`backend/tests/test_roster_breakdowns.py`
(`test_get_departments_collapses_casing_duplicates`,
`test_get_departments_real_file_returns_29`,
`test_get_data_quality_warnings_flags_designation_casing_mismatch`).

## Multi-value fields — handling rule

`Client as on June 2026` and `Project Manager` can each hold multiple
entries in one cell, separated inconsistently (commas, "and", slashes).
Until confirmed otherwise with the business owner:

- Treat these as a single free-text field for display and for the
  employee-level table — do not silently split and re-count without
  flagging it, since a naive split can misattribute an employee to the
  wrong client/PM count.
- For any chart that counts headcount **by client**, first ask whether
  an employee "on multiple clients" should be counted once per client
  they support, or once total under a combined label. Do not guess this
  silently — it changes headcount totals materially.
- `"Client TBD"` / `"PM TBD"` = bench/unallocated. This is a meaningful
  category on its own (don't drop these rows, and don't lump them into
  "other").

## Confirmed Power BI model structure (from the actual model, not guessed)

The live Power BI model has **five tables**: `HR MASTER` (the roster),
`Sheet1` (the daily booking data), `Calendar`, `Available Months`, and
`UtilizationLongTable` (the utilization ground truth). This section
lists every measure/calculated column name visible in the model's
Fields pane — this is the **definitive target list** to replicate, not
a guess. Formula bodies are not yet visible from these screenshots
(the Fields pane only shows names) — see "What's still needed" below.

### HR MASTER — measures and calculated columns

Headcount/status: `Active Employees`, `Active %`, `Inactive Employees`,
`Total Employees`, `Opening Headcount`, `Closing Headcount`, `Net Change`

Attrition: `Attrition %`, `Exits`, `Joiners`, `Voluntary Leavers`,
`InVoluntary Leavers`

Org splits: `GCC Employees`, `Non GCC Employees`, `Grades`, `Departments`,
`Skills`, `Skills Covered`, `Seniority Levels`, `Locations Covered`,
`Clients Covered`, `Markets Covered`, `Projects`, `Project Managers`

Experience: `Average Experience (Yrs)`, `Average Hexaware Experience`,
`Experience Band` (calculated column), `Experience Band Sort`
(calculated column)

Segmentation: `Senior - Lead Employees`, `Strategic Pool`,
`Seniority Category` (calculated column), `Home Workforce Category`
(calculated column), `Pending Mapping Count` — **this is very likely
the actual "bench/unallocated" metric**, i.e. what we'd been calling
bench count probably corresponds to this measure. Use this exact name
and confirm its logic once the DAX is visible, rather than inventing a
separately-named bench metric.

### Sheet1 (booking) — measures and calculated columns

Hours: `Hours`, `Average Hours`, `Total Hours`, `Client Hours`,
`Internal Hours`, `Client Hours %`, `Internal Hours %`

Scope/coverage: `Total Clients`, `Total Projects`, `Total Regions`,
`Total Employeess` (typo present in the real model — keep it exact),
`Markets Covered`, `Reporting Period`, `Selected Week`,
`Current Selection`, `Month Year` (calculated column)

### UtilizationLongTable — measures and calculated columns

`Weekly Utilization %`, `Average Weekly Utilization %`,
`Period Total Utilization %`, `Average Period Utilization %`,
`Employee Period Utilization %`, `Latest Week Utilization %`,
`Employee Count`, `Reporting Employees`, `Utilization Band`
(calculated column), `Utilization Band Sort` (calculated column)

The presence of both a `Weekly Utilization %` and a separate
`Employee Period Utilization %` and `Average Period Utilization %`
confirms there are at least three distinct utilization aggregation
levels in the real model — do not collapse these into one "utilization"
metric; replicate all three as named.

### Calendar / Available Months

Standard date-table pattern: `Date`, `Month Start`, `Month End`,
`Month Year`, `Month Sort` — used for period navigation/filtering
across the whole report. Build an equivalent date dimension in the
backend rather than deriving months ad hoc from row dates.

### What's still needed to finish "100% validated"

These screenshots show measure **names**, not their DAX formula bodies.
Before data-agent can replicate the logic exactly, get one of:

1. Screenshots of each measure's formula bar (click the measure in
   Power BI Desktop, the DAX shows above the table), for at least the
   core metrics (`Active Employees`, `Attrition %`, `Pending Mapping
   Count`, `Weekly Utilization %`, `Period Total Utilization %`), or
2. The `.pbix` file itself opened in Power BI Desktop so the formulas
   can be read directly, or
3. Use of DAX Studio / the Model view's "View DAX" export, which lists
   every measure's formula in one place — this is the fastest option if
   available.

Without the formula text, data-agent can still build a best-effort
version of each metric from the `data-model` definitions already
written above, but it cannot be marked "validated" until reconciled
against the real formula or the ground-truth values it produces.

## Confirmed real DAX formulas (verbatim from the live Power BI model)

These are the actual DAX bodies for all 48 measures/calculated columns
listed in "Confirmed Power BI model structure" above, provided directly
by the business owner from the live model. **These supersede every
provisional definition below and in "Derived metrics" — where they
disagree with a provisional guess, the DAX here is correct, fix the
provisional definition/implementation to match, don't silently keep both.**

```dax
Active % =
DIVIDE([Active Employees], [Total Employees])

Active Employees =
CALCULATE([Total Employees], 'HR Master'[Status] = "Active")

Attrition % =
DIVIDE([Exits], [Closing Headcount] + [Exits])

Average Experience (Yrs) =
AVERAGE('HR MASTER'[Total Experience])

Average Hexaware Experience =
AVERAGE('HR Master'[Hexaware Experience (Years)])

Average Hours =
AVERAGE('Sheet1'[Hours])

Average Period Utilization % =
AVERAGEX(
    VALUES('UtilizationLongTable'[Employee]),
    CALCULATE(MAX('UtilizationLongTable'[Period Total Utilization %]))
)

Average Weekly Utilization % =
AVERAGE('UtilizationLongTable'[Weekly Utilization %])

Client Hours =
CALCULATE([Total Hours], 'Sheet1'[Hours Type] = "Client Hours")

Client Hours % =
DIVIDE([Client Hours], [Total Hours])

Clients Covered =
CALCULATE(
    DISTINCTCOUNT('HR MASTER'[Client as on June 2026]),
    'HR MASTER'[Client as on June 2026] <> BLANK(),
    NOT CONTAINSSTRING('HR MASTER'[Client as on June 2026], "Client TBD")
)

Closing Headcount =
VAR EndDate = EOMONTH(MAX('Available Months'[Month Start]), 0)
RETURN
CALCULATE(
    [Total Employees],
    FILTER(
        'HR Master',
        'HR Master'[DOJ (DEPT)] <= EndDate &&
        (ISBLANK('HR Master'[LWD]) || 'HR Master'[LWD] > EndDate)
    )
)

Current Selection =
VAR MonthSel = SELECTEDVALUE('Sheet1'[Month Year], "All Months")
VAR RegionSel = SELECTEDVALUE('Sheet1'[Region (EC)], "All Regions")
VAR MarketSel = SELECTEDVALUE('Sheet1'[Market (EC)], "All Markets")
RETURN MonthSel & "  |  " & RegionSel & "  |  " & MarketSel

Departments =
DISTINCTCOUNT('HR MASTER'[Designation ])

Employee Count =
DISTINCTCOUNT('UtilizationLongTable'[Employee])

Employee Period Utilization % =
MAX('UtilizationLongTable'[Period Total Utilization %])

Exits =
VAR StartDate = MIN('Available Months'[Month Start])
VAR EndDate = EOMONTH(MAX('Available Months'[Month Start]), 0)
RETURN
CALCULATE(
    [Total Employees],
    FILTER(
        'HR MASTER',
        NOT ISBLANK('HR MASTER'[LWD]) &&
        'HR MASTER'[LWD] >= StartDate &&
        'HR MASTER'[LWD] <= EndDate
    )
)

GCC Employees =
CALCULATE([Total Employees], 'HR Master'[Type] = "GCC")

Grades =
DISTINCTCOUNT('HR Master'[Grade])

Inactive Employees =
CALCULATE([Total Employees], 'HR Master'[Status] = "Inactive")

Internal Hours =
CALCULATE([Total Hours], 'Sheet1'[Hours Type] = "Internal Hours")

Internal Hours % =
DIVIDE([Internal Hours], [Total Hours])

InVoluntary Leavers =
CALCULATE([Exits], 'HR Master'[Reason for Leaving] = "Involuntary")

Joiners =
VAR StartDate = MIN('Available Months'[Month Start])
VAR EndDate = EOMONTH(MAX('Available Months'[Month Start]), 0)
RETURN
CALCULATE(
    [Total Employees],
    FILTER(
        'HR MASTER',
        'HR MASTER'[DOJ (DEPT)] >= StartDate &&
        'HR MASTER'[DOJ (DEPT)] <= EndDate
    )
)

Latest Week Utilization % =
VAR LatestWeek =
    CALCULATE(MAX('UtilizationLongTable'[Week Start]), ALL('UtilizationLongTable'[Week Start]))
RETURN
CALCULATE([Average Weekly Utilization %], 'UtilizationLongTable'[Week Start] = LatestWeek)

Locations Covered =
DISTINCTCOUNT('HR MASTER'[WORK_LOCATION])

Markets Covered =
DISTINCTCOUNT('Sheet1'[Market (EC)])

Net Change =
[Joiners] - [Exits]

Non GCC Employees =
CALCULATE([Total Employees], 'HR Master'[Type] = "Non GCC")

Opening Headcount =
VAR StartDate = MIN('Calendar'[Date])
VAR PreviousDate = StartDate - 1
RETURN
CALCULATE(
    [Total Employees],
    FILTER(
        'HR Master',
        'HR MASTER'[DOJ (DEPT)] <= PreviousDate &&
        (ISBLANK('HR Master'[LWD]) || 'HR Master'[LWD] > PreviousDate)
    )
)

Pending Mapping Count =
CALCULATE(
    [Total Employees],
    FILTER(
        'HR Master',
        CONTAINSSTRING('HR MASTER'[Client as on June 2026], "Client TBD")
        || CONTAINSSTRING('HR Master'[Project Manager], "PM TBD")
        || CONTAINSSTRING('HR Master'[Skill], "Skill TBD")
        || CONTAINSSTRING('HR MASTER'[DEPUTATION], "Deputation TBD")
        || CONTAINSSTRING('HR MASTER'[Seniorirty Level], "Seniority TBD")
        || CONTAINSSTRING('HR Master'[Type], "Type TBD")
    )
)

Project Managers =
CALCULATE(DISTINCTCOUNT('HR Master'[Project Manager]), 'HR Master'[Project Manager] <> BLANK())

Projects =
DISTINCTCOUNT('HR MASTER'[Client as on June 2026])

Reporting Employees =
CALCULATE(
    DISTINCTCOUNT('UtilizationLongTable'[Employee]),
    FILTER('UtilizationLongTable', NOT ISBLANK('UtilizationLongTable'[Weekly Utilization %]))
)

Reporting Period =
FORMAT(MIN('Sheet1'[Date]), "MMM yyyy") & " - " & FORMAT(MAX('Sheet1'[Date]), "MMM yyyy")

Selected Week =
VAR WeekValue = SELECTEDVALUE('Sheet1'[Week Start])
RETURN IF(ISBLANK(WeekValue), "All Weeks / Multiple Weeks", FORMAT(WeekValue, "dd-mmm-yyyy"))

Senior - Lead Employees =
CALCULATE(
    [Total Employees],
    FILTER(
        'HR MASTER',
        CONTAINSSTRING('HR MASTER'[Seniority Levels], "Senior")
            || CONTAINSSTRING('HR MASTER'[Seniority Levels], "Lead")
    )
)

Seniority Levels =
CALCULATE(
    DISTINCTCOUNT('HR MASTER'[Seniorirty Level]),
    'HR MASTER'[Seniorirty Level] <> BLANK(),
    NOT CONTAINSSTRING('HR MASTER'[Seniorirty Level], "Seniority TBD")
)

Skills =
DISTINCTCOUNT('HR MASTER'[Primary Skill])

Skills Covered =
CALCULATE(
    DISTINCTCOUNT('HR Master'[Skill]),
    'HR Master'[Skill] <> BLANK(),
    NOT CONTAINSSTRING('HR Master'[Skill], "TBD")
)

Strategic Pool =
CALCULATE([Total Employees], FILTER('HR MASTER', ISBLANK('HR MASTER'[DOJ (DEPT)])))

Total Clients =
DISTINCTCOUNT('Sheet1'[Holding])

Total Employees =
DISTINCTCOUNT('HR MASTER'[NEW_EMP_ID])

Total Employeess =
DISTINCTCOUNT('Sheet1'[Employee])

Total Hours =
SUM('Sheet1'[Hours])

Total Projects =
DISTINCTCOUNT('Sheet1'[Project])

Total Regions =
DISTINCTCOUNT('Sheet1'[Region (EC)])

Voluntary Leavers =
CALCULATE([Exits], 'HR Master'[Reason for Leaving] = "Voluntary")
```

### Corrections this section forces vs. the provisional definitions below

- **`Total Employees` is `DISTINCTCOUNT('HR MASTER'[NEW_EMP_ID])` — NOT filtered
  by `Status`.** It counts every distinct employee ID regardless of
  active/inactive. `Active Employees` / `Inactive Employees` are the
  ones that filter by `Status`, each built as `CALCULATE([Total Employees], ...)`.
- **`Closing Headcount` / `Opening Headcount` are date-based**, using
  `DOJ (DEPT)` and `LWD` against a selected month-end/month-start from
  `Available Months`/`Calendar` — **independent of `Status`**. Do not
  conflate these with `Active Employees`. An employee could be
  `Status = Inactive` but still counted in `Closing Headcount` if their
  `LWD` is after the period end (and vice versa in edge cases) — the
  date filter is authoritative, not the `Status` field.
- **`Joiners` uses `DOJ (DEPT)`**, not `DOJ (Hexaware)` as the earlier
  provisional definition guessed — it's an internal-transfer-aware
  measure, consistent with `Closing Headcount`/`Opening Headcount` also
  using `DOJ (DEPT)`.
- **`Exits` uses `LWD` falling within the selected period** (`Available Months`
  min/max), not just "`Status = Inactive`".
- **`Attrition %` denominator is `Closing Headcount + Exits`**, not
  `Active Employees + Inactive Employees` as the provisional definition
  guessed.
- **`Pending Mapping Count` checks SIX fields for a "TBD" marker**:
  `Client as on June 2026` ("Client TBD"), `Project Manager` ("PM TBD"),
  `Skill` ("Skill TBD"), `DEPUTATION` ("Deputation TBD"), `Seniorirty Level`
  ("Seniority TBD"), and `Type` ("Type TBD") — not just Client/PM as
  previously guessed. Note this checks the raw `Skill` and `Type`
  columns for a literal "TBD" substring, which assumes those columns can
  actually contain values like `"Skill TBD"`/`"Type TBD"` in the source
  data — confirm this against real values, don't assume it silently
  matches nothing.
- **`Clients Covered` and `Projects` (on `HR MASTER`) both count
  DISTINCT RAW STRING VALUES of the messy `Client as on June 2026`
  column** — including multi-value combinations as their own distinct
  value (e.g. `"Managed Services, Scandlines, Inter Milan and Blackroll"`
  counts as ONE distinct value, not four). `Clients Covered` additionally
  excludes blanks and any value containing `"Client TBD"`. **Replicate
  this exactly as the messy/naive DISTINCTCOUNT it is — do not "fix" it
  to count real individual clients**, since that would no longer match
  the live model's output.
- **`Total Clients` / `Total Projects` / `Total Regions` / `Markets Covered`
  are the clean booking-sheet equivalents** — `DISTINCTCOUNT` over
  `Sheet1[Holding]`, `Sheet1[Project]` (note: `Project`, not the
  documented `Project Name` — confirm the real booking-sheet column
  name), `Sheet1[Region (EC)]`, `Sheet1[Market (EC)]` respectively — one
  clean value per row, not the roster's messy multi-value strings.

### Flagged discrepancies — do not silently resolve, ask first

- **RESOLVED (2026-07-15):** `Senior - Lead Employees` references
  `'HR MASTER'[Seniority Levels]` (plural), which does not exist as a
  physical column in the real roster file — only `Seniorirty Level`
  (singular, typo'd, matching the documented column) exists. **Confirmed
  by the business owner: treat these as the same column** — this is a
  naming inconsistency within the DAX itself, not a missing/separate
  column. `get_senior_lead_employees()` in
  `backend/app/services/roster_metrics.py` is implemented against the
  real `Seniorirty Level` column as a confirmed proxy for the DAX's
  `Seniority Levels`, using CONTAINSSTRING's case-sensitive substring
  match (result: 36 on the real file). Note the source data has a
  casing-duplicate issue for this column (e.g. "Standard Senior" vs
  "Standard senior", "Standard Lead" vs "Premium lead") — rows that only
  match "senior"/"lead" in non-standard casing are excluded from this
  case-sensitive count and instead surfaced as a
  `seniority_level_casing_mismatch` data-quality warning.
- **`Weekly Utilization %` and `Period Total Utilization %` are
  calculated columns on `UtilizationLongTable` whose formula bodies are
  still missing** — only measures were exported/provided, not
  calculated columns, and every measure above that depends on them
  (`Average Weekly Utilization %`, `Average Period Utilization %`,
  `Employee Period Utilization %`, `Latest Week Utilization %`) is only
  as correct as those two underlying calculated columns, which remain
  unverified. **Any utilization metric already built must be marked
  provisional/unverified in code (docstring/comment) until these two
  calculated-column formulas are provided** — do not treat the measures
  above as fully validating utilization just because the aggregation
  layer around them is now known.

## Derived metrics — provisional definitions (pending real DAX)

These were our best-guess definitions before the real model was visible.
Now that the measure names are confirmed above, treat these as
provisional mappings to the real measures — keep the naming aligned to
the real model (e.g. use `Pending Mapping Count`, not "bench count") so
there's no drift between what we build and what the model actually calls
things. Confirm the real formula for each before calling it validated.

- **`Active Employees`** = count of rows where `Status = "Active"` (our earlier "Headcount")
- **`Inactive Employees`** = count of rows where `Status = "Inactive"` (our earlier "Attrition count")
- **`Attrition %`** = `Inactive Employees` ÷ (`Active Employees` + `Inactive Employees`), for a given period — confirm the real denominator/period logic once the DAX is visible
- **`Voluntary Leavers`** / **`InVoluntary Leavers`** = split of `Inactive Employees` by `Reason for Leaving` — confirmed as two separate real measures, not one split
- **`Pending Mapping Count`** = likely count of active rows where `Client as on June 2026` / `Project Manager` contains `"TBD"` — confirm this mapping against the real formula, don't assume
- **`GCC Employees`** / **`Non GCC Employees`** = split by `Type` — confirmed as two separate real measures
- **`Average Experience (Yrs)`** = mean of `Total Experience` over active headcount
- **`Average Hexaware Experience`** = mean of `Hexaware Experience (Years)` over active headcount
- **`Joiners`** = count where `DOJ (Hexaware)` falls within the selected period
- Compliance rate (`Declaration Signed = "Yes"` ÷ total) has no confirmed matching measure name yet in the real model — check whether it exists before building it as a new metric

## Second data source — time booking sheet

A second sheet exists, structured very differently from the employee
roster: **one row per employee, per project, per week**, with booked
hours. This is a normalized fact table and is the correct source for
any per-client or per-project headcount/allocation metric — do not
derive those from the roster's messy `Client as on June 2026` field
when this table is available.

### Column dictionary (booking sheet)

| Column | Meaning | Notes |
|---|---|---|
| `Region (EC)` / `Market (EC)` / `Segment (EC)` | Org hierarchy, similar to but a separate taxonomy from the roster's `Region`/`Market` | Confirm whether "EC" here is a different reporting hierarchy before assuming it matches the roster's `Region`/`Market` values |
| `Global Department` | High-level function | e.g. `Creative`, `Engineering` |
| `Department` | Sub-function | e.g. `QA`, `Creative Content`, `Back-end Development` |
| `Team (EC)` | Internal team code | e.g. `CMUS` |
| `Holding` | **The actual client/account name** | e.g. `Arcadis GBV`, `CFL Ventures`, `ParsonsKellogg`, `Dept Holding BV`. This is the clean, one-value-per-row equivalent of the roster's messy multi-client field. |
| `Project Name` | Specific project/engagement | e.g. `ARD26-88008 - Arcadis Website Launch` |
| `Project URL` | Link to the internal project tool | Not needed for dashboard metrics |
| `Employee` | Employee full name | **Free text, "First Last" format — see join risk below** |
| `Month` | Reporting month | e.g. `Apr 26` |
| `Monday of Week` | The week-bucket key (always a Monday) | Used to group daily entries into a week |
| `Date` | The actual day the hours were logged | **Confirmed from the full file: this varies day-by-day within the week (e.g. `2026-04-13` through `2026-04-19`) — it does NOT always equal `Monday of Week`. This sheet is daily granularity, one row per employee/project/day/hours-type. An earlier read of a small sample wrongly suggested these were always equal — they are not, at full scale.** |
| `Booked Hours Type` | `Client Hours` vs `Internal Hours` | Basis for utilization metrics |
| `Employee Booked Hours` | Hours booked that day, that project, that type | Decimal. Sum by `Employee` + `Monday of Week` to get weekly totals. |

### Resolving the earlier multi-client ambiguity

**Use this booking table, not the roster's `Client` field, for any
"headcount by client" or "allocation by project" metric.** Since it's
one row per employee per project per week, headcount-by-client becomes
a straightforward distinct-employee-count per `Holding` for a given
period — no parsing or splitting of comma-separated text required, and
no double-counting ambiguity, since an employee genuinely booking hours
against multiple clients in a period will correctly appear once per
client here.

### New derived metrics available from this table

- **Utilization rate** = sum(`Client Hours`) ÷ sum(`Client Hours` + `Internal Hours`), per employee or per team, per period
- **Billable hours** = sum of `Employee Booked Hours` where `Booked Hours Type = "Client Hours"`
- **Headcount by client/project** = count of distinct `Employee` values per `Holding` (or `Project Name`) for a given period
- **Bench cross-check** = employees who appear in the roster as active but have zero or near-zero `Client Hours` in a recent period — a stronger bench signal than the roster's `Client TBD` flag alone, since it's based on actual logged time rather than a static field

### Join risk between the two sheets — confirmed findings from the real files

Checked against the actual uploaded files (52-row roster, 40 distinct
employees in the booking sheet, 41 in the ground-truth utilization
sheet), matching on first-name + last-name tokens (ignoring middle
names and whitespace):

- **Booking sheet → roster: 40/40 matched.** No blocker here.
- **Ground-truth utilization sheet → roster: 36/41 matched, 5 unresolved:**
  (all findings below this point are from the ORIGINAL 258-row booking
  file; see "UPDATE (2026-07-15)" further down for the re-run against the
  new 1523-row / 7-week file, which now has 46 distinct employees)
  - `Ankit Singh` — does not appear anywhere in the 52-row roster.
    **RESOLVED (2026-07-15): confirmed to be a typo for `Amit Singh`
    (`AMIT KUMAR SINGH` in the roster) — see `known-name-variants.md`
    for the full evidence.**
  - `Kaginthala Reddy` → likely `KAGITHALA  LOKESH REDDY` in the roster
    (transposed letters: "Kaginthala" vs "Kagithala", plus a dropped
    middle name)
  - `Pramod Kabugande` → likely `PRAMOD  KABUGADE` in the roster (extra
    "n" — "Kabugande" vs "Kabugade")
  - `Saumyarajan Kanungo` → likely `SAUMYARANJAN  KANUNGO` in the roster
    ("Saumyarajan" vs "Saumyaranjan")
  - `Suraj Kayade` → likely `SURAJ CHHATRAPATI KAVADE` in the roster
    ("Kayade" vs "Kavade", plus a dropped middle name)

These four spelling-variant cases are genuine source-data inconsistencies,
not a normalization bug — a first+last token match resolves 36/41
cleanly, but the remaining 5 need either a manual name-mapping table
(build one, don't guess silently) or a cleaner ID if one exists upstream.
`Ankit Singh` specifically is now confirmed (see below and
`known-name-variants.md`) to be a typo for `Amit Singh` /
`AMIT KUMAR SINGH`. See `known-name-variants.md` in this folder for the
full mapping — the `Ankit Singh`/`Amit Singh` entry there is confirmed,
the other 4 remain best-guess pending sign-off.

**UPDATE (2026-07-15), re-run against the new booking file:** the new
`UTILIZATION DATA SHEET.xlsx` has **46 distinct employees** (up from 40).
Re-ran booking → roster matching using token-subset matching (booking
name's tokens ⊆ roster name's tokens, or ≥2 shared tokens) — **46/46
matched (100%)**, still no blocker on this join direction. Separately,
matching booking-sheet employee names directly against the ground-truth
`Utilization_Long` sheet's employee names (needed for the utilization
reconciliation below, not the roster join) found 36/46 exact matches, +4
of the same known variants already listed above (just observed from the
opposite direction this time — the booking sheet has the "typo'd"
spelling and the ground truth has the "corrected" one, e.g. booking's
`Kagithala Reddy` vs ground truth's `Kaginthala Reddy`), + 1 case flagged
at the time as unresolved: booking's `Amit Singh` vs ground truth's
`Ankit Singh`. **RESOLVED (2026-07-15): confirmed to be the same
person/typo as the `Ankit Singh`-not-in-roster case above — both trace
back to the same ground-truth spelling error. See
`known-name-variants.md` for the full evidence.** 5 booking-only employees
(`Kuldeep Mehra`, `Prashant Bakle`, `Shivam Soni`, `Nikita Sankpal`,
`Anchal Kumari Singh`) and several ground-truth-only employees
(`Amaan Khan`, `Aman Jaiswal`, `Ashok Rajani`, `Siraj Pathan`, plus
`Ankit Singh`) have no counterpart at all in the overlapping-week
comparison — not necessarily an error, may just mean no data was logged
for them in the specific overlapping weeks checked.

### RESOLVED (2026-07-15): overlapping week now exists, reconciliation run

The booking sheet was replaced with a new export
(`UTILIZATION DATA SHEET.xlsx`, filename also changed) covering **1523
rows / 7 weeks, `2026-04-13` through `2026-05-25`** (up from 258 rows / 2
weeks). The ground-truth workbook (`PowerBI_Ready_Utilization_May_2026.xlsx`,
filename unchanged) turned out to have **3 real sheets** —
`README` (documentation/index, 2-column, not data), `Employee_Weekly_Wide`
(41 rows, one row per employee, 4 weekly columns + `Period Total
Utilization %`), and `Utilization_Long` (164 rows, one row per
employee/week, `Week Start` `2026-05-04` through `2026-05-25`). Both data
sheets have their real header in row 0 — only `README` has a preamble.
Read via `utilization_metrics.load_ground_truth_long()` /
`load_ground_truth_wide()` in
`backend/app/services/utilization_metrics.py`.

**The booking sheet's last 4 weeks (`2026-05-04` .. `2026-05-25`) now
overlap `Utilization_Long` exactly.** Reconciliation was run (152
matched employee/weeks, after applying 4 of the 5 known name variants
from `known-name-variants.md`, direction reversed: booking-sheet spelling
→ ground-truth spelling). **Formula A is confirmed correct**:

- **Formula A** (Client Hours ÷ actual logged total that week) — 143/152
  (94.1%) match the ground truth's `Weekly Utilization %` within a
  0.0006 tolerance (half the sheet's 3-decimal rounding step).
- **Formula B** (fixed 45hr capacity denominator) — only 122/152 (80.3%)
  match. **Ruled out.**

The remaining 9/152 rows (`Harsh Kharbanda`, `Lodagala Suresh`, `Suraj
Kayade` — all partial-week loggers) are within ~0.3-0.4 percentage
points of Formula A but not bit-exact. Root cause NOT confirmed — most
likely a small number of extra/missing booking rows for those three
employees in those specific weeks, or day-level rounding upstream of the
export. Logged as an open, named residual
(`utilization_formula_a_residual_mismatch`), not smoothed over.

**RESOLVED (2026-07-15): booking sheet's `Amit Singh` = ground truth's
`Ankit Singh` = roster's `AMIT KUMAR SINGH`, confirmed same person.**
Evidence: neither spelling appears more than once across sheets (no
sheet has both `Amit` and `Ankit Singh` as distinct rows), all 4
overlapping weeks (`2026-05-04`..`2026-05-25`) match exactly on
Region/Market/Global Department/Department/Team, and the booking
sheet's 100%-`Client Hours` pattern for those weeks exactly reproduces
the ground truth's `Weekly Utilization % = 1.0` for the same 4 weeks
under Formula A. Canonical name: `Amit Singh` (2 of 3 sources — roster
and booking sheet — agree on "Amit"; only the ground-truth sheet has
the "Ankit" typo). Mapping added to `known-name-variants.md`. This also
closes the earlier `Ankit Singh`-not-in-roster open question — it was
the same underlying typo, not a separate unlisted employee.

## Third data source — utilization summary (validation ground truth)

A third sheet exists: **one row per employee, per week**, with a
pre-computed utilization percentage. This is almost certainly a DAX
output from the current Power BI model — treat it as the **ground-truth
reference for testing**, not as raw input to re-aggregate from scratch.

### Column dictionary (utilization summary sheet)

| Column | Meaning | Notes |
|---|---|---|
| `Global Department` / `Department` | Same taxonomy as the booking sheet | |
| `Employee` | Employee full name | Same `"First Last"` format and same join risk as the booking sheet's `Employee` column |
| `Region (EC)` / `Market (EC)` | Same taxonomy as the booking sheet | |
| `Week Start` | The Monday of that week | Format `YYYY-MM-DD` |
| `Weekly Utilization %` | Utilization for that employee, that single week | Color-coded in the source (green ≥ ~90%, amber ~80%) — colors are presentation only, don't encode them as data |
| `Period Total Utilization %` | Utilization averaged/aggregated across the whole period shown for that employee | **Constant across every week-row for a given employee in this export** — confirm whether this is a fixed reporting-period average (e.g. the month or quarter) rather than a running/cumulative figure, since it does not change week to week per employee |

### Why this table matters more than it looks

This sheet is the answer to "100% validated and tested as per our data."
Once data-agent computes utilization independently from the booking
sheet's raw `Client Hours`/`Internal Hours` (Utilization = Client Hours ÷
total booked hours, per the earlier definition), **that computed value
must match this sheet's `Weekly Utilization %` exactly, employee by
employee, week by week.** Any mismatch means either the utilization
formula's denominator assumption is wrong (e.g. wrong standard
weekly-capacity figure, such as assuming 40 hours when the real Power BI
model uses a different one), or a data-cleaning step upstream is
dropping/duplicating booking rows.

### Task for data-agent once both sheets are available — DONE (2026-07-15)

Completed once the booking sheet's week range extended into May and
overlapped `Utilization_Long`. Result: Formula A confirmed (94.1% exact
match, see "RESOLVED" section above for full numbers and the residual
5.9%). Implemented in `backend/app/services/utilization_metrics.py`
(`compute_weekly_utilization_formula_a`, `get_weekly_utilization_pct`,
`reconcile_weekly_utilization`), tested in
`backend/tests/test_utilization_metrics.py` (includes 5 permanent
regression cases, step 4 below). Original task steps kept for reference:

1. For a handful of employee + week combinations that appear in **both**
   the booking sheet and this utilization sheet (same `Week Start` /
   `Monday of Week`), independently compute utilization from the raw
   booked hours.
2. Compare against this sheet's `Weekly Utilization %` for the same
   employee/week. They must match exactly (or within a defined rounding
   tolerance, e.g. 0.1%).
3. If they don't match, do not adjust the reference sheet's numbers to
   fit — treat this sheet as correct and find the discrepancy in the
   computed side (wrong capacity assumption, missed rows, wrong date
   alignment between `Monday of Week` and `Week Start`).
4. Once the formula is confirmed correct against several known weeks,
   write it as a tested function and keep 3-5 of these known
   employee/week/value combinations as permanent regression tests in
   `backend/tests/` — so future changes to the data pipeline can't
   silently break utilization numbers without a test failing.

1. `Total Experience` == `Hexaware Experience (Years)` + `Before Hexaware Experience` for every row (flag mismatches, don't silently recompute and overwrite)
2. `LWD` and `Reason for Leaving` are populated only when `Status = "Inactive"`, and vice versa
3. `GRADE` sorts using the explicit ordinal list, never alphabetically
4. Row counts before/after any cleaning step are logged, so silent row drops are caught
5. Any join between the roster and the booking sheet reports its match rate (what % of `Employee` values resolved to a `NEW_EMP_ID`) — a low match rate means the name-normalization step needs work, not that the data is fine
6. Independently-computed utilization matches the utilization summary sheet's `Weekly Utilization %` exactly for every employee/week combination present in both sheets — this is the definitive correctness test for the whole data layer, not an optional nice-to-have
