"""
Tests for backend/app/services/roster_metrics.py.

Two layers per function-group:
- A hand-built fixture of known rows with a hand-computed expected value
  (fast, deterministic, doesn't depend on the real Excel file staying
  unchanged).
- One regression test against the real roster file, asserting the exact
  values computed and verified by hand in the task (see comments) so a
  future data or logic change that shifts these numbers is caught.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.roster_metrics import (
    DEFAULT_ROSTER_PATH,
    get_active_employees,
    get_active_pct,
    get_attrition_pct,
    get_average_experience_yrs,
    get_average_hexaware_experience,
    get_clients_covered,
    get_closing_headcount,
    get_data_quality_warnings,
    get_exits,
    get_gcc_employees,
    get_inactive_employees,
    get_involuntary_leavers,
    get_joiners,
    get_non_gcc_employees,
    get_opening_headcount,
    get_pending_mapping_count,
    get_projects,
    get_senior_lead_employees,
    get_skills_covered,
    get_total_employees,
    get_voluntary_leavers,
    load_roster,
)


SAMPLE_TODAY = "30-Jun-26"  # snapshot date, used as one of the calendar boundaries
JUNE_2026 = pd.Timestamp("2026-06-01")
# `_resolve_period(df, period_month=JUNE_2026)` (explicit single month):
#   Start=2026-06-01, End=2026-06-30, Previous=2026-05-31 (start - 1 day).
# `_resolve_period(df)` (no arg -> default, full dataset range): see the
# full-range tests below — Start/End/Previous span the whole fixture's
# DOJ (DEPT)/LWD/Today range, not just June 2026.

_COMMON_DEFAULTS = {
    "Today": SAMPLE_TODAY,
    "Skill": "QA",
    "DEPUTATION": "OFFSHORE",
    "Seniorirty Level": "Standard Mid",
}


@pytest.fixture
def sample_roster() -> pd.DataFrame:
    """
    7 hand-built rows (June 2026 period, Today = 30-Jun-26):
      - 4 Active (2 GCC, 2 Non GCC)
      - 2 Inactive (1 Voluntary, 1 Involuntary)
      - 1 Active row has a Total Experience mismatch (data-quality case)
      - 1 Active row has TBD client, 1 Active row has TBD PM
      - E2 DOJ (DEPT) = 15-Jun-26 -> a Joiner this period
      - E5 LWD = 10-Jun-26 -> an Exit this period, still counts in
        Closing Headcount as excluded (LWD <= EndDate)
      - E6 LWD = 15-Jan-26 -> LWD is before the period, so NOT an Exit
        this period, and also excluded from Closing Headcount (LWD is
        not > EndDate... wait LWD <= EndDate so excluded correctly)
      - E7 Active, Skill = "Skill TBD" -> exercises the Skill-TBD branch
        of Pending Mapping Count (confirmed 0 rows have this in the real
        file, but the branch itself must still work if it ever occurs)
    """
    rows = [
        {
            "NEW_EMP_ID": "E1",
            "Status": "Active",
            "Type": "GCC",
            "Hexaware Experience (Years)": 2.0,
            "Before Hexaware Experience": 3.0,
            "Total Experience": 5.0,  # consistent
            "Client as on June 2026": "Acme Corp",
            "Project Manager": "Jane Doe",
            "Reason for Leaving": None,
            "DOJ (DEPT)": "1-Jan-26",
            "LWD": None,
        },
        {
            "NEW_EMP_ID": "E2",
            "Status": "Active",
            "Type": "GCC",
            "Hexaware Experience (Years)": 1.0,
            "Before Hexaware Experience": 1.0,
            "Total Experience": 2.0,  # consistent
            "Client as on June 2026": "Client TBD",
            "Project Manager": "PM TBD",
            "Reason for Leaving": None,
            "DOJ (DEPT)": "15-Jun-26",  # Joiner this period
            "LWD": None,
        },
        {
            "NEW_EMP_ID": "E3",
            "Status": "Active",
            "Type": "Non GCC",
            "Hexaware Experience (Years)": 4.0,
            "Before Hexaware Experience": 2.0,
            "Total Experience": 6.0,  # consistent
            "Client as on June 2026": "Beta Inc",
            "Project Manager": "PM TBD",  # PM-only TBD
            "Reason for Leaving": None,
            "DOJ (DEPT)": "1-Jan-26",
            "LWD": None,
        },
        {
            "NEW_EMP_ID": "E4",
            "Status": "Active",
            "Type": "Non GCC",
            "Hexaware Experience (Years)": 3.0,
            "Before Hexaware Experience": 3.0,
            "Total Experience": 999.0,  # MISMATCH: should be 6.0
            "Client as on June 2026": "Gamma LLC",
            "Project Manager": "John Roe",
            "Reason for Leaving": None,
            "DOJ (DEPT)": "1-Jan-26",
            "LWD": None,
        },
        {
            "NEW_EMP_ID": "E5",
            "Status": "Inactive",
            "Type": "GCC",
            "Hexaware Experience (Years)": 5.0,
            "Before Hexaware Experience": 1.0,
            "Total Experience": 6.0,
            "Client as on June 2026": "Delta Co",
            "Project Manager": "Amy Lee",
            "Reason for Leaving": "Voluntary",
            "DOJ (DEPT)": "1-Jan-25",
            "LWD": "10-Jun-26",  # Exit this period
        },
        {
            "NEW_EMP_ID": "E6",
            "Status": "Inactive",
            "Type": "GCC",
            "Hexaware Experience (Years)": 6.0,
            "Before Hexaware Experience": 2.0,
            "Total Experience": 8.0,
            "Client as on June 2026": "Epsilon",
            "Project Manager": "Sam Fox",
            "Reason for Leaving": "Involuntary",
            "DOJ (DEPT)": "1-Jan-25",
            "LWD": "15-Jan-26",  # LWD before the period -> not an Exit
        },
        {
            "NEW_EMP_ID": "E7",
            "Status": "Active",
            "Type": "GCC",
            "Hexaware Experience (Years)": 2.0,
            "Before Hexaware Experience": 1.0,
            "Total Experience": 3.0,
            "Client as on June 2026": "Zeta Corp",
            "Project Manager": "Amy Lee",
            "Reason for Leaving": None,
            "DOJ (DEPT)": "1-Jan-26",
            "LWD": None,
            "Skill": "Skill TBD",
        },
    ]
    df = pd.DataFrame(rows)
    for col, default in _COMMON_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
        else:
            df[col] = df[col].fillna(default)
    return df


def test_get_active_employees(sample_roster):
    # E1,E2,E3,E4 are Active -> 4
    assert get_active_employees(sample_roster) == 5


def test_get_inactive_employees(sample_roster):
    # E5,E6 are Inactive -> 2
    assert get_inactive_employees(sample_roster) == 2


def test_get_total_employees(sample_roster):
    # DISTINCTCOUNT(NEW_EMP_ID) over ALL rows, not Status-filtered -> 7
    assert get_total_employees(sample_roster) == 7


def test_get_active_pct(sample_roster):
    # 5/7 * 100 = 71.4286
    assert get_active_pct(sample_roster) == pytest.approx(71.4286, abs=0.01)


def test_get_active_pct_empty():
    assert get_active_pct(pd.DataFrame(columns=["Status", "NEW_EMP_ID"])) == 0.0


def test_get_closing_headcount(sample_roster):
    # Explicit period_month=June 2026 -> EndDate = 2026-06-30.
    # DOJ (DEPT) <= EndDate AND (LWD blank OR LWD > EndDate):
    #   E1 DOJ 1-Jan-26, LWD blank -> counted
    #   E2 DOJ 15-Jun-26, LWD blank -> counted
    #   E3 DOJ 1-Jan-26, LWD blank -> counted
    #   E4 DOJ 1-Jan-26, LWD blank -> counted
    #   E5 DOJ 1-Jan-25, LWD 10-Jun-26 (not > EndDate) -> excluded
    #   E6 DOJ 1-Jan-25, LWD 15-Jan-26 (not > EndDate) -> excluded
    #   E7 DOJ 1-Jan-26, LWD blank -> counted
    # -> 5
    assert get_closing_headcount(sample_roster, period_month=JUNE_2026) == 5


def test_get_opening_headcount(sample_roster):
    # Explicit period_month=June 2026 -> PreviousDate = 2026-05-31.
    # DOJ (DEPT) <= PreviousDate AND (LWD blank OR LWD > PreviousDate):
    #   E1 DOJ 1-Jan-26 <= prev, LWD blank -> counted
    #   E2 DOJ 15-Jun-26 NOT <= prev -> excluded
    #   E3 DOJ 1-Jan-26 <= prev, LWD blank -> counted
    #   E4 DOJ 1-Jan-26 <= prev, LWD blank -> counted
    #   E5 DOJ 1-Jan-25 <= prev, LWD 10-Jun-26 > prev -> counted (still
    #       "employed" as of end of May)
    #   E6 DOJ 1-Jan-25 <= prev, LWD 15-Jan-26 NOT > prev -> excluded
    #   E7 DOJ 1-Jan-26 <= prev, LWD blank -> counted
    # -> 5 (E1, E3, E4, E5, E7)
    assert get_opening_headcount(sample_roster, period_month=JUNE_2026) == 5


def test_get_joiners(sample_roster):
    # Explicit period_month=June 2026 -> DOJ (DEPT) within
    # [2026-06-01, 2026-06-30]: only E2 (15-Jun-26) -> 1
    assert get_joiners(sample_roster, period_month=JUNE_2026) == 1


def test_get_exits(sample_roster):
    # Explicit period_month=June 2026 -> LWD non-blank and within
    # [2026-06-01, 2026-06-30]:
    #   E5 LWD=10-Jun-26 -> yes
    #   E6 LWD=15-Jan-26 -> outside the period -> no
    # -> 1
    assert get_exits(sample_roster, period_month=JUNE_2026) == 1


def test_get_attrition_pct(sample_roster):
    # Explicit period_month=June 2026 -> Exits=1, Closing Headcount=5
    # -> 1 / (5+1) * 100 = 16.6667
    assert get_attrition_pct(sample_roster, period_month=JUNE_2026) == pytest.approx(
        16.6667, abs=0.01
    )


# --------------------------------------------------------------------------
# Default period (no period_month passed) = full dataset date range
# --------------------------------------------------------------------------
#
# For `sample_roster`: DOJ (DEPT) values are 1-Jan-25 (E5,E6), 1-Jan-26
# (E1,E3,E4,E7), 15-Jun-26 (E2) -> earliest_date = 2025-01-01.
# Today=30-Jun-26, max(DOJ)=2026-06-15, max(LWD)=2026-06-10 -> latest
# candidate = 2026-06-30 -> latest month = June 2026.
# So StartDate=2025-01-01, EndDate=2026-06-30 (EOMONTH of June 2026),
# PreviousDate = earliest_date - 1 day = 2024-12-31.


def test_get_closing_headcount_default_full_range(sample_roster):
    # EndDate=2026-06-30, same as the explicit-June case above (June 2026
    # is both the fixture's only month with events near "now" and the
    # latest month in the derived range) -> 5, same as explicit case.
    assert get_closing_headcount(sample_roster) == 5


def test_get_opening_headcount_default_full_range(sample_roster):
    # PreviousDate = 2024-12-31, one day before the earliest DOJ (DEPT)
    # in the fixture (2025-01-01) -> no one has DOJ (DEPT) <= 2024-12-31
    # -> 0, by construction (see _resolve_period docstring).
    assert get_opening_headcount(sample_roster) == 0


def test_get_joiners_default_full_range(sample_roster):
    # StartDate=2025-01-01, EndDate=2026-06-30 -> every row with a
    # parseable DOJ (DEPT) falls in range: E1,E2,E3,E4,E5,E6,E7 -> 7
    assert get_joiners(sample_roster) == 7


def test_get_exits_default_full_range(sample_roster):
    # StartDate=2025-01-01, EndDate=2026-06-30 -> both E5 (10-Jun-26) and
    # E6 (15-Jan-26) now fall within the full range -> 2
    assert get_exits(sample_roster) == 2


def test_get_attrition_pct_default_full_range(sample_roster):
    # Exits=2, Closing Headcount=5 -> 2 / (5+2) * 100 = 28.5714
    assert get_attrition_pct(sample_roster) == pytest.approx(28.5714, abs=0.01)


def test_get_voluntary_leavers(sample_roster):
    # only E5 is Voluntary
    assert get_voluntary_leavers(sample_roster) == 1


def test_get_involuntary_leavers(sample_roster):
    # only E6 is Involuntary
    assert get_involuntary_leavers(sample_roster) == 1


def test_get_gcc_employees(sample_roster):
    # E1, E2, E5, E6, E7 -> 5
    assert get_gcc_employees(sample_roster) == 5


def test_get_non_gcc_employees(sample_roster):
    # E3, E4 -> 2
    assert get_non_gcc_employees(sample_roster) == 2


def test_get_average_experience_yrs(sample_roster):
    # active rows Total Experience: 5.0, 2.0, 6.0, 999.0, 3.0 (mismatch
    # row included as-is, per "never silently fix" rule) -> mean = 203.0
    assert get_average_experience_yrs(sample_roster) == pytest.approx(203.0)


def test_get_average_hexaware_experience(sample_roster):
    # active rows Hexaware Experience: 2.0, 1.0, 4.0, 3.0, 2.0 -> mean = 2.4
    assert get_average_hexaware_experience(sample_roster) == pytest.approx(2.4)


def test_get_pending_mapping_count(sample_roster):
    # Six-field check, NO Status filter:
    #   E2: Client TBD + PM TBD -> yes
    #   E3: PM TBD -> yes
    #   E7: Skill TBD -> yes
    # -> 3
    assert get_pending_mapping_count(sample_roster) == 3


def test_get_clients_covered(sample_roster):
    # distinct Client as on June 2026, excluding blank/"Client TBD":
    # Acme Corp, Beta Inc, Gamma LLC, Delta Co, Epsilon, Zeta Corp -> 6
    # (E2's "Client TBD" is excluded)
    assert get_clients_covered(sample_roster) == 6


def test_get_projects(sample_roster):
    # naive DISTINCTCOUNT of Client as on June 2026, no exclusions:
    # Acme Corp, Client TBD, Beta Inc, Gamma LLC, Delta Co, Epsilon,
    # Zeta Corp -> 7 distinct values (one per row here, since none repeat)
    assert get_projects(sample_roster) == 7


def test_get_senior_lead_employees():
    # Dedicated small fixture (sample_roster's rows all default to
    # "Standard Mid", which matches neither substring, so this needs its
    # own cases): case-sensitive CONTAINSSTRING on "Senior"/"Lead".
    #   S1: "Standard Senior" -> matches "Senior" -> counted
    #   S2: "Standard Lead" -> matches "Lead" -> counted
    #   S3: "Premium Mid" -> matches neither -> not counted
    #   S4: "Premium lead" (lowercase "lead") -> case-sensitive miss -> not counted
    #   S5: "Seniority TBD" -> does NOT contain "Senior" as a substring
    #       ("Seniority" != "Senior" + more text is fine, but check:
    #       "Seniority TBD" does contain "Senior" as a literal substring
    #       ("Senior" + "ity TBD") -> counted
    # -> hand count: S1, S2, S5 counted = 3; S3, S4 not counted
    df = pd.DataFrame(
        [
            {"NEW_EMP_ID": "S1", "Seniorirty Level": "Standard Senior"},
            {"NEW_EMP_ID": "S2", "Seniorirty Level": "Standard Lead"},
            {"NEW_EMP_ID": "S3", "Seniorirty Level": "Premium Mid"},
            {"NEW_EMP_ID": "S4", "Seniorirty Level": "Premium lead"},
            {"NEW_EMP_ID": "S5", "Seniorirty Level": "Seniority TBD"},
        ]
    )
    assert get_senior_lead_employees(df) == 3


def test_get_senior_lead_employees_casing_mismatch_flagged_as_warning():
    df = pd.DataFrame(
        [
            {
                "NEW_EMP_ID": "S4",
                "Status": "Active",
                "Hexaware Experience (Years)": 1.0,
                "Before Hexaware Experience": 1.0,
                "Total Experience": 2.0,
                "Seniorirty Level": "Premium lead",
            }
        ]
    )
    warnings = get_data_quality_warnings(df)
    assert any(w["type"] == "seniority_level_casing_mismatch" for w in warnings)


def test_get_data_quality_warnings_flags_mismatch(sample_roster):
    warnings = get_data_quality_warnings(sample_roster)
    types = [w["type"] for w in warnings]
    assert "total_experience_mismatch" in types
    mismatch_warning = next(w for w in warnings if w["type"] == "total_experience_mismatch")
    assert mismatch_warning["row_id"] == "E4"


def test_get_data_quality_warnings_flags_unexpected_status():
    df = pd.DataFrame(
        [
            {
                "NEW_EMP_ID": "E7",
                "Status": "On Leave",  # unexpected value
                "Hexaware Experience (Years)": 1.0,
                "Before Hexaware Experience": 1.0,
                "Total Experience": 2.0,
            }
        ]
    )
    warnings = get_data_quality_warnings(df)
    assert any(w["type"] == "unexpected_status_value" for w in warnings)


# --------------------------------------------------------------------------
# Skills Covered
# --------------------------------------------------------------------------


def test_get_skills_covered_sample_roster(sample_roster):
    # All 7 rows default to Skill="QA" (_COMMON_DEFAULTS) except E7, which
    # overrides to "Skill TBD" -> excluded by the CONTAINSSTRING(...,"TBD")
    # filter. Only distinct non-TBD value left is "QA" -> 1.
    assert get_skills_covered(sample_roster) == 1


def test_get_skills_covered_hand_built_fixture():
    # Dedicated fixture exercising blank/NaN and "TBD"-substring exclusion
    # plus a genuine duplicate, per the real DAX:
    #   CALCULATE(DISTINCTCOUNT(Skill), Skill<>BLANK(), NOT CONTAINSSTRING(Skill,"TBD"))
    df = pd.DataFrame(
        {
            "NEW_EMP_ID": ["A1", "A2", "A3", "A4", "A5", "A6"],
            "Skill": ["Front End", "QA", "Front End", None, "Skill TBD", "Mobile"],
        }
    )
    # Distinct non-blank, non-TBD values: Front End, QA, Mobile -> 3
    assert get_skills_covered(df) == 3


def test_get_skills_covered_real_file(real_roster):
    # Confirmed on the real roster file: 16 distinct `Skill` values, no
    # blanks, no "TBD" substrings present today. Matches the Power BI
    # reference exactly (unlike naively counting `Primary Skill`, which
    # returns 20 and is the wrong column per the real DAX).
    assert get_skills_covered(real_roster) == 16


# --------------------------------------------------------------------------
# Regression tests against the real roster file
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_roster() -> pd.DataFrame:
    if not DEFAULT_ROSTER_PATH.exists():
        pytest.skip(f"real roster file not present at {DEFAULT_ROSTER_PATH}")
    return load_roster()


def test_real_roster_headcount(real_roster):
    # Computed via: df['Status'].value_counts() -> Active 47, Inactive 5
    assert get_total_employees(real_roster) == 52
    assert get_active_employees(real_roster) == 47
    assert get_inactive_employees(real_roster) == 5
    assert get_active_pct(real_roster) == pytest.approx(90.3846, abs=0.01)


def test_real_roster_date_based_headcount_explicit_june_2026(real_roster):
    # Explicit period_month=June 2026 (matches the old single-month
    # default, kept as a regression test for the explicit-period path).
    # FIXED (2026-07-16, DAX BLANK() semantics bug): the 2 rows with
    # literal "TBD" in DOJ (DEPT) (NEW_EMP_ID 2000194634, 2000195658 --
    # Rahul Malhotra, Shorya Sharma) parse to NaT. In real DAX, BLANK()
    # in a date comparison behaves like epoch-zero, so
    # `DOJ (DEPT) <= EndDate` is TRUE for a blank -- both rows are Active
    # with blank LWD, so both now correctly count in Closing/Opening
    # Headcount (previously wrongly excluded by pandas' NaT-always-False
    # comparison). Recomputed by hand with the corrected semantics:
    #   Closing Headcount (DOJ<=2026-06-30 & (LWD blank | LWD>2026-06-30)) = 47
    #   Opening Headcount (DOJ<=2026-05-31 & (LWD blank | LWD>2026-05-31)) = 46
    #   Joiners (DOJ in [2026-06-01, 2026-06-30]) = 2 (unaffected -- blank
    #       DOJ (DEPT) never satisfies `>= StartDate` under DAX's
    #       blank-as-zero semantics either, same as before)
    #   Exits (LWD in [2026-06-01, 2026-06-30]) = 1 (NEW_EMP_ID 2000172791,
    #       LWD=15-Jun-26) -- unaffected, no LWD is blank/TBD
    june = pd.Timestamp("2026-06-01")
    assert get_closing_headcount(real_roster, period_month=june) == 47
    assert get_opening_headcount(real_roster, period_month=june) == 46
    assert get_joiners(real_roster, period_month=june) == 2
    assert get_exits(real_roster, period_month=june) == 1


def test_real_roster_date_based_headcount_default_full_range(real_roster):
    # DEFAULT (no period_month) = full dataset date range, per explicit
    # user decision. Computed by hand via pandas:
    #   DOJ (DEPT) min/max = 2025-07-07 / 2026-06-16
    #   LWD max = 2026-06-15; Today = 2026-06-26
    #   -> earliest_date = 2025-07-07 (MIN DOJ (DEPT))
    #   -> latest month = June 2026 (max of Today/DOJ max/LWD max, all
    #      fall in June 2026) -> EndDate = 2026-06-30
    #   -> StartDate = 2025-07-01 (first of earliest month)
    #   -> PreviousDate = 2025-07-06 (earliest_date - 1 day)
    # FIXED (2026-07-16, DAX BLANK() semantics bug): same 2 TBD-DOJ rows
    # as above. Blank DOJ (DEPT) behaves like epoch-zero in DAX, so it is
    # ALWAYS <= any EndDate/PreviousDate, no matter how early -- both
    # rows now count in Closing Headcount AND (a genuinely new
    # consequence, not previously anticipated) in the full-range Opening
    # Headcount too, since "always <= any date" includes PreviousDate =
    # 2025-07-06. This overturns the earlier "full-range Opening
    # Headcount is 0 by construction" reasoning for these 2 rows
    # specifically -- that reasoning only holds for rows with a real,
    # parseable DOJ (DEPT).
    #   Closing Headcount (DOJ<=2026-06-30 & (LWD blank|LWD>2026-06-30)) = 47
    #   Opening Headcount (DOJ<=2025-07-06 & (LWD blank|LWD>2025-07-06)) = 2
    #       (only the 2 blank-DOJ rows qualify -- every other row's real
    #       DOJ (DEPT) is after 2025-07-06)
    #   Joiners (DOJ in [2025-07-01, 2026-06-30]) = 50 (unaffected -- blank
    #       DOJ (DEPT) never satisfies `>= StartDate`)
    #   Exits (LWD in [2025-07-01, 2026-06-30]) = 5 (unaffected)
    assert get_closing_headcount(real_roster) == 47
    assert get_opening_headcount(real_roster) == 2
    assert get_joiners(real_roster) == 50
    assert get_exits(real_roster) == 5


def test_real_roster_attrition_explicit_june_2026(real_roster):
    # Attrition % = Exits / (Closing Headcount + Exits) * 100
    # FIXED (2026-07-16, DAX BLANK() semantics bug): Closing Headcount for
    # June 2026 is now 47 (was 45), so recomputed:
    #             = 1 / (47 + 1) * 100 = 2.0833%
    june = pd.Timestamp("2026-06-01")
    assert get_attrition_pct(real_roster, period_month=june) == pytest.approx(
        2.0833, abs=0.01
    )
    # Reason for Leaving among the 5 inactive rows: Involuntary=3, Voluntary=2
    assert get_involuntary_leavers(real_roster) == 3
    assert get_voluntary_leavers(real_roster) == 2


def test_real_roster_attrition_default_full_range(real_roster):
    # DEFAULT (no period_month) = full range. FIXED (2026-07-16, DAX
    # BLANK() semantics bug): Closing Headcount is now 47 (was 45, see
    # test_real_roster_date_based_headcount_default_full_range) -> Exits=5
    # -> 5 / (47 + 5) * 100 = 9.6154%.
    # This now matches the Power BI reference PDF's ~9.6% Attrition
    # closely (previously 10.0% vs ~9.6%, off because Closing Headcount
    # was wrongly 45 instead of 47 -- see data-model SKILL.md "Known open
    # data gap", now resolved).
    assert get_attrition_pct(real_roster) == pytest.approx(9.6154, abs=0.01)


def test_real_roster_doj_dept_unparseable_warning(real_roster):
    # 2 rows have the literal string "TBD" in DOJ (DEPT) (NEW_EMP_ID
    # 2000194634, 2000195658) -- confirmed by hand via
    # df[df['DOJ (DEPT)'] == 'TBD']. These must be surfaced, not silently
    # excluded/coerced without a trace.
    warnings = get_data_quality_warnings(real_roster)
    doj_warnings = [w for w in warnings if w["type"] == "doj_dept_unparseable"]
    assert len(doj_warnings) == 2
    assert {w["row_id"] for w in doj_warnings} == {2000194634, 2000195658}


def test_real_roster_org_split(real_roster):
    # Type value_counts(): GCC=48, Non GCC=4
    assert get_gcc_employees(real_roster) == 48
    assert get_non_gcc_employees(real_roster) == 4


def test_real_roster_experience(real_roster):
    # active['Total Experience'].mean() == 9.17531914893617
    assert get_average_experience_yrs(real_roster) == pytest.approx(9.1753, abs=0.001)
    # active['Hexaware Experience (Years)'].mean() == 0.9321276595744681
    assert get_average_hexaware_experience(real_roster) == pytest.approx(0.9321, abs=0.001)


def test_real_roster_pending_mapping_count(real_roster):
    # Six-field check per the real DAX, NO Status filter (FIXED from the
    # earlier Active-only, Client/PM-only count of 5). Computed by hand:
    #   Client as on June 2026 contains "Client TBD": 9 rows
    #   Project Manager contains "PM TBD": 9 rows
    #   Seniorirty Level contains "Seniority TBD": 7 rows
    #   Skill contains "Skill TBD": 0 rows (column never has this value
    #       in the current file -- flagged, not a bug)
    #   DEPUTATION contains "Deputation TBD": 0 rows (DEPUTATION is
    #       100% "OFFSHORE" in this file)
    #   Type contains "Type TBD": 0 rows (Type is only "GCC"/"Non GCC")
    # OR'd together, deduplicated by employee -> 10
    assert get_pending_mapping_count(real_roster) == 10


def test_real_roster_clients_covered_and_projects(real_roster):
    # Clients Covered: distinct Client as on June 2026, excluding blanks
    # and "Client TBD" -> 31 (computed by hand via
    # df.loc[mask, 'Client as on June 2026'].nunique())
    assert get_clients_covered(real_roster) == 31
    # Projects (HR MASTER): naive DISTINCTCOUNT of the same raw column,
    # no exclusions -> 32 (one more than Clients Covered because
    # "Client TBD" itself counts as one more distinct raw value)
    assert get_projects(real_roster) == 32


def test_real_roster_senior_lead_employees(real_roster):
    # Computed via: df['Seniorirty Level'].value_counts() on the real file:
    #   Standard Lead (12), Premium Senior (8), Standard Senior (8),
    #   Seniority TBD (7), Premium lead (5), Premium Mid (4),
    #   Standard Mid (3), Hexa Sr (2), Premium Lead (1),
    #   Standard senior (1), Premium Technical Service Delivery Manager (1)
    # Case-SENSITIVE CONTAINSSTRING match on "Senior"/"Lead" (matches
    # DAX's CONTAINSSTRING default, which is case-sensitive unlike SEARCH):
    #   Standard Lead (12) + Premium Senior (8) + Standard Senior (8) +
    #   Seniority TBD (7, "Senior" is a literal substring of "Seniority")
    #   + Premium Lead (1) = 36, all distinct NEW_EMP_ID -> 36
    # NOT matched: "Premium lead" (5, lowercase "lead"), "Standard senior"
    # (1, lowercase "senior"), "Premium Mid" (4), "Standard Mid" (3),
    # "Hexa Sr" (2), "Premium Technical Service Delivery Manager" (1).
    assert get_senior_lead_employees(real_roster) == 36


def test_real_roster_no_experience_mismatches(real_roster):
    # Confirmed by hand: (Hexaware + Before - Total).abs() > 0.01 -> 0 rows
    warnings = get_data_quality_warnings(real_roster)
    mismatch_warnings = [w for w in warnings if w["type"] == "total_experience_mismatch"]
    assert mismatch_warnings == []
