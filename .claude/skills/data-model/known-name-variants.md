# Known name variants — roster vs booking/utilization sheets

Do not treat this file as confirmed truth yet — the mappings below are
data-agent's best fuzzy-match guess, verified only by first+last token
matching. Get explicit confirmation (from the user or the business
owner) before relying on these in production metrics, especially for
`Ankit Singh`, which has no candidate match at all.

| Name as it appears in booking / utilization sheets | Best-guess match in roster (`NAME` column) | Confidence |
|---|---|---|
| Kaginthala Reddy | KAGITHALA  LOKESH REDDY | High — transposed letters + dropped middle name |
| Pramod Kabugande | PRAMOD  KABUGADE | High — single extra letter |
| Saumyarajan Kanungo | SAUMYARANJAN  KANUNGO | High — single letter swap |
| Suraj Kayade | SURAJ CHHATRAPATI KAVADE | Medium — surname spelling differs (Kayade vs Kavade), plus dropped middle name |

## RESOLVED AT SOURCE (2026-07-16): `Ankit Singh` corrected to `Amit Singh` directly in the ground-truth Excel file

Per explicit business-owner direction, the `Ankit Singh` typo documented as CONFIRMED below
has now been corrected **directly in the source Excel file**
(`backend/data/PowerBI_Ready_Utilization_May_2026.xlsx`), not just handled as a code-level
mapping. Every occurrence of the string `"Ankit Singh"` was replaced with `"Amit Singh"`
across all 3 sheets (`README`, `Employee_Weekly_Wide`, `Utilization_Long`) using `openpyxl`
cell-level edits (row counts unchanged: 41 rows in `Employee_Weekly_Wide`, 164 rows in
`Utilization_Long`). A pre-fix backup is kept at
`backend/data/backups/PowerBI_Ready_Utilization_May_2026.xlsx.bak-20260716-182414`.

This is **different from the earlier "known variant, handled via code-level mapping"
status below** — that described a workaround for an upstream data problem that still
existed in the source file. As of 2026-07-16 the upstream source itself is fixed: the
ground-truth file now spells this employee's name `Amit Singh` everywhere, matching the
roster and booking sheet. Any code-level name-mapping logic for this specific
`Ankit Singh` → `Amit Singh` case is now redundant against the cleaned source and should
be treated as a harmless safety net only, not as compensating for a live data issue. The
`test_reconciliation_confirms_formula_a` regression test in
`backend/tests/test_utilization_metrics.py` was updated accordingly: `matched_employee_weeks`
rose from 152 to 156 (4 additional employee/weeks — this employee's 4 rows — now match by
plain string equality instead of falling through as unmatched), and `formula_a_exact_matches`
rose from 143 to 147 (all 4 newly-matched weeks are exact matches).

## CONFIRMED (2026-07-15): `Ankit Singh` (ground truth) = `Amit Singh` (booking sheet) = `AMIT KUMAR SINGH` (roster)

This resolves the previously-open "`Ankit Singh` has no match at all" question and the
separately-flagged "`Amit Singh` (booking) vs `Ankit Singh` (ground truth) — could be same
person or two different people" question. Both were the same underlying typo. Evidence,
checked directly against the three source files:

- **Roster**: contains `AMIT KUMAR SINGH` (`NAME` column). No `Ankit Singh` / `ANKIT SINGH`
  exists anywhere in the 52-row roster — confirmed by direct substring search, not fuzzy
  matching. The roster's own spelling is "Amit", not "Ankit".
- **Booking sheet** (`UTILIZATION DATA SHEET.xlsx`): has 23 rows for `Amit Singh` — no
  `Ankit Singh` row exists anywhere in this sheet.
- **Ground truth** (`Utilization_Long`): has exactly 4 rows for `Ankit Singh`, weeks
  `2026-05-04`, `05-11`, `05-18`, `05-25` — no `Amit Singh` row exists anywhere in this sheet.
  Since no sheet contains *both* spellings as distinct rows, this cannot be two different
  people double-listed in one source — it's one person, two spellings across two exports.
- **Metadata match is exact** for all 4 overlapping weeks: `Region (EC)=EMEA`,
  `Market (EC)=DACH`, `Global Department=Engineering`, `Department=Front-end Development`,
  `Team (EC)=DTDE` (booking sheet) all match the ground truth's `Region (EC)=EMEA`,
  `Market (EC)=DACH`, `Global Department=Engineering`, `Department=Front-end Development`
  for the same weeks.
- **Hours pattern is fully consistent with the reported utilization**: booking-sheet
  `Amit Singh` logged 100% `Client Hours` (zero `Internal Hours`) in every one of those 4
  weeks (45, 18, 36, 45 hours respectively — partial weeks for 05-11/05-18, but all client
  time). Ground truth's `Weekly Utilization %` for `Ankit Singh` is exactly `1.0` (100%) for
  all 4 of the same weeks — which is exactly what Formula A (`Client Hours ÷ actual logged
  hours that week`, already confirmed as the correct utilization formula elsewhere in this
  skill) predicts for a 100%-client-hours employee, regardless of the total hours logged.
  This is not just plausible overlap — the numbers reconcile exactly.
- The Power BI reference PDF's "Employee Period Utilization % by Employee" list showing
  `Ankit Singh` at 100% is not independent evidence of the "Ankit" spelling being correct —
  that page is built directly from `UtilizationLongTable`, the same ground-truth sheet that
  has the typo, so the PDF just reflects the same source error, not a separate confirmation.

**Decision: treat as the same person. Canonical name = `Amit Singh`** (matches both the
roster's real first name, in `AMIT KUMAR SINGH`, and the booking sheet's spelling — 2 of 3
sources agree on "Amit"; only the ground-truth sheet has "Ankit"). `Ankit Singh` in
`Utilization_Long` is a data-entry typo for `Amit Singh`, not a separate/unlisted employee.
When joining booking-sheet or roster records against `Utilization_Long`, map
`Ankit Singh` → `Amit Singh` the same way the other 4 confirmed variants above are mapped
(reversed direction: here the ground truth has the typo, not the booking sheet).

## How to use this file

Once confirmed, this becomes a static lookup table in the data-access
layer — join on it explicitly rather than re-running fuzzy matching at
query time, so results are stable and auditable. Update this file (and
re-confirm) whenever the source roster or booking export changes
significantly.
