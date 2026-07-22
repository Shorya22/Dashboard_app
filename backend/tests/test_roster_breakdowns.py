"""
Tests for the breakdown/trend/list aggregation functions added to
backend/app/services/roster_metrics.py in the Phase 5 pass (Main,
HR Portal Home, HR Analytics, Workforce, Skills & Experience, and
Employee Directory reference pages).

Same two-layer pattern as test_roster_metrics.py: a hand-built fixture
with a hand-computed expected value, plus a regression test against the
real roster file for the values verified by hand in the task (see
comments).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.services.validation.engine import apply_dataset_defaults

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

from app.services.roster_metrics import (
    DEFAULT_ROSTER_PATH,
    _experience_band,
    _seniority_category,
    get_data_quality_warnings,
    get_departments,
    get_employee_directory,
    get_exits_table,
    get_headcount_by_region,
    get_headcount_by_seniority,
    get_month_wise_closing_headcount,
    get_month_wise_resignation,
    get_monthly_joiners_vs_leavers,
    get_skill_bifurcation_by_experience_band,
    get_skill_bifurcation_by_region,
    get_skill_bifurcation_by_seniority_category,
    get_status_split,
    get_strategic_pool,
    get_voluntary_involuntary_split,
    get_workforce_by_experience_band,
    get_workforce_by_seniority_category,
    get_workforce_by_type,
    get_workforce_by_working_entity,
    get_workforce_category_split,
    get_workforce_details_by_region,
    load_roster,
)


@pytest.fixture
def sample_roster() -> pd.DataFrame:
    """
    6 hand-built rows spanning Region/Working Entity/Seniority/
    Experience/Type/Skill so every breakdown function has a
    hand-checkable expected value.
    """
    rows = [
        {
            "NEW_EMP_ID": "E1",
            "NAME": "Alice  Smith",
            "Status": "Active",
            "Type": "GCC",
            "Region": "EMEA",
            "Market": "UKI",
            "Working Entity": "DTUK",
            "GRADE": "G5",
            "Designation": "Engineer",
            "WORK_LOCATION": "LONDON",
            "Primary Skill": "Front End",
            "Seniorirty Level": "Standard Senior",
            "Total Experience": 6.0,
            "Client": "Acme Corp",
            "SUPERVISOR (Hexaware)": "Bob  Jones",
            "DOJ (DEPT)": "1-Jan-26",
            "LWD": None,
            "Reason for Leaving": None,
        },
        {
            "NEW_EMP_ID": "E2",
            "NAME": "Bob Lee",
            "Status": "Active",
            "Type": "Non GCC",
            "Region": "AMER",
            "Market": "AMER",
            "Working Entity": "AMER",
            "GRADE": "G4",
            "Designation": "Analyst",
            "WORK_LOCATION": "NYC",
            "Primary Skill": "Front End",
            "Seniorirty Level": "Standard Lead",
            "Total Experience": 0.5,
            "Client": "Client TBD",
            "SUPERVISOR (Hexaware)": "Amy Fox",
            "DOJ (DEPT)": "1-Feb-26",
            "LWD": None,
            "Reason for Leaving": None,
        },
        {
            "NEW_EMP_ID": "E3",
            "NAME": "Cara Diaz",
            "Status": "Inactive",
            "Type": "GCC",
            "Region": "EMEA",
            "Market": "DACH",
            "Working Entity": "DTDE",
            "GRADE": "G6",
            "Designation": "QA Lead",
            "WORK_LOCATION": "BERLIN",
            "Primary Skill": "QA",
            "Seniorirty Level": "Premium Mid",
            "Total Experience": 2.0,
            "Client": "Beta Inc",
            "SUPERVISOR (Hexaware)": "Amy Fox",
            "DOJ (DEPT)": "1-Jan-25",
            "LWD": "10-Mar-26",
            "Reason for Leaving": "Voluntary",
        },
        {
            "NEW_EMP_ID": "E4",
            "NAME": "Dev Patel",
            "Status": "Inactive",
            "Type": "GCC",
            "Region": "AMER",
            "Market": "AMER",
            "Working Entity": "AMER",
            "GRADE": "G5",
            "Designation": "Consultant",
            "WORK_LOCATION": "NYC",
            "Primary Skill": "QA",
            "Seniorirty Level": "Seniority TBD",
            "Total Experience": 4.0,
            "Client": "Gamma LLC",
            "SUPERVISOR (Hexaware)": "Bob  Jones",
            "DOJ (DEPT)": "1-Jan-25",
            "LWD": "5-Apr-26",
            "Reason for Leaving": "Involuntary",
        },
        {
            "NEW_EMP_ID": "E5",
            "NAME": "Eve Wu",
            "Status": "Active",
            "Type": "GCC",
            "Region": "EMEA",
            "Market": "UKI",
            "Working Entity": "DTUK",
            "GRADE": "G8",
            "Designation": "Director",
            "WORK_LOCATION": "LONDON",
            "Primary Skill": "Salesforce",
            "Seniorirty Level": "Hexa Sr",
            "Total Experience": 10.0,
            "Client": "Delta Co",
            "SUPERVISOR (Hexaware)": "Amy Fox",
            "DOJ (DEPT)": "1-Jan-25",
            "LWD": None,
            "Reason for Leaving": None,
        },
        {
            "NEW_EMP_ID": "E6",
            "NAME": "Finn Ortiz",
            "Status": "Active",
            "Type": "Non GCC",
            "Region": None,
            "Market": None,
            "Working Entity": None,
            "GRADE": "G3A",
            "Designation": "Trainee",
            "WORK_LOCATION": "PUNE",
            "Primary Skill": "Salesforce",
            "Seniorirty Level": "Premium Technical Service Delivery Manager",
            "Total Experience": None,
            "Client": None,
            "SUPERVISOR (Hexaware)": "Bob Jones",
            "DOJ (DEPT)": None,
            "LWD": None,
            "Reason for Leaving": None,
        },
    ]
    df = pd.DataFrame(rows)
    df["Today"] = "30-Jun-26"
    return df


# --------------------------------------------------------------------------
# Simple splits
# --------------------------------------------------------------------------


def test_get_strategic_pool(sample_roster):
    # Strategic Pool is now `Status == "Strategic Pool"` (2026-07-21), not
    # blank DOJ (DEPT). No fixture row carries that status, so -> 0.
    # Under the old blank-DOJ definition this returned 1 (E6), while E6 was
    # ALSO counted as Active — the double-count that made Home and HR Home
    # disagree. See metric_invariants.py.
    assert get_strategic_pool(sample_roster) == 0


def test_get_workforce_category_split(sample_roster):
    # UPDATED (2026-07-22): this is now the same Status group-by as
    # status_split, scoped to the present workforce — so like that donut it
    # reflects the statuses actually in the data. The fixture has no
    # Strategic Pool rows, so that slice is absent rather than an explicit 0.
    # Both buckets come from one `Status` group-by, so they can never
    # double-count an employee or disagree with HR Home's Status Split.
    assert get_workforce_category_split(sample_roster) == {"Active": 4}


def test_get_status_split(sample_roster):
    # UPDATED (2026-07-22): the donut simply reflects the Status column —
    # slices are whatever statuses the data contains, nothing declared in
    # config first. This fixture has no Strategic Pool rows, so that slice
    # is absent rather than shown as an explicit 0.
    assert get_status_split(sample_roster) == {"Active": 4, "Inactive": 2}
    assert sum(get_status_split(sample_roster).values()) == len(sample_roster)


def test_status_split_reflects_a_brand_new_status(sample_roster):
    """A status the business starts using appears on its own."""
    df = sample_roster.copy()
    df.loc[df.index[0], "Status"] = "Sabbatical"
    split = get_status_split(df)
    assert split["Sabbatical"] == 1
    assert sum(split.values()) == len(df)


def test_get_workforce_by_type(sample_roster):
    # GCC: E1,E3,E4,E5 -> 4; Non GCC: E2,E6 -> 2
    assert get_workforce_by_type(sample_roster) == {"GCC": 4, "Non GCC": 2}


def test_get_headcount_by_region(sample_roster):
    # EMEA: E1,E3,E5 -> 3; AMER: E2,E4 -> 2. E6's Region is blank and is
    # now counted as "Region TBD" rather than dropped, so the bars still
    # add up to the headline employee count instead of quietly falling short.
    assert get_headcount_by_region(sample_roster) == {
        "EMEA": 3,
        "AMER": 2,
        "Region TBD": 1,
    }
    assert sum(get_headcount_by_region(sample_roster).values()) == len(sample_roster)


def test_get_workforce_by_working_entity(sample_roster):
    # E6's Working Entity is blank -> "Entity TBD", not dropped.
    assert get_workforce_by_working_entity(sample_roster) == {
        "DTUK": 2,
        "AMER": 2,
        "DTDE": 1,
        "Entity TBD": 1,
    }
    assert sum(
        get_workforce_by_working_entity(sample_roster).values()
    ) == len(sample_roster)


def test_get_headcount_by_seniority(sample_roster):
    # No casing dupes in sample_roster, so each row's label just gets
    # title-cased (already title-case in the fixture -> unchanged), plus
    # the "Tbd" -> "TBD" restoration for the TBD marker.
    assert get_headcount_by_seniority(sample_roster) == {
        "Standard Senior": 1,
        "Standard Lead": 1,
        "Premium Mid": 1,
        "Seniority TBD": 1,
        "Hexa Sr": 1,
        "Premium Technical Service Delivery Manager": 1,
    }


def test_get_headcount_by_seniority_collapses_casing_duplicates():
    # Regression test for the confirmed bug: "Premium Lead"/"Premium lead"
    # and "Standard Senior"/"Standard senior" must collapse into one key
    # each instead of splitting into separate bars.
    #
    # Hand-built fixture mirrors the real roster's confirmed counts:
    #   "Premium Lead" (1 row) + "Premium lead" (5 rows) -> 6
    #   "Standard Senior" (8 rows) + "Standard senior" (1 row) -> 9
    rows = []
    for i in range(1):
        rows.append({"NEW_EMP_ID": f"PL{i}", "Seniorirty Level": "Premium Lead"})
    for i in range(5):
        rows.append({"NEW_EMP_ID": f"pl{i}", "Seniorirty Level": "Premium lead"})
    for i in range(8):
        rows.append({"NEW_EMP_ID": f"SS{i}", "Seniorirty Level": "Standard Senior"})
    for i in range(1):
        rows.append({"NEW_EMP_ID": f"ss{i}", "Seniorirty Level": "Standard senior"})
    df = pd.DataFrame(rows)

    result = get_headcount_by_seniority(df)

    # Show work: 1 + 5 = 6, 8 + 1 = 9.
    assert result == {"Premium Lead": 6, "Standard Senior": 9}


# --------------------------------------------------------------------------
# Departments / Designation casing (2026-07-16 fix)
# --------------------------------------------------------------------------


def test_get_departments_collapses_casing_duplicates():
    # Regression test for the confirmed bug: "SalesForce Core Developer"/
    # "Salesforce Core Developer" must collapse into one distinct
    # Designation instead of counting as two separate departments.
    rows = [
        {"NEW_EMP_ID": "D1", "Designation": "SalesForce Core Developer"},
        {"NEW_EMP_ID": "D2", "Designation": "SalesForce Core Developer"},
        {"NEW_EMP_ID": "D3", "Designation": "Salesforce Core Developer"},
        {"NEW_EMP_ID": "D4", "Designation": "Salesforce Core Developer"},
        {"NEW_EMP_ID": "D5", "Designation": "Front End Developer"},
    ]
    df = pd.DataFrame(rows)

    # Naive nunique() would return 3 ("SalesForce...", "Salesforce...",
    # "Front End Developer"); normalized count must be 2.
    assert get_departments(df) == 2


def test_get_departments_real_file_returns_27():
    # Regression test locking in the resolution: normalizing the
    # SalesForce/Salesforce casing duplicate brought Departments from 30
    # down to 29, matching the Power BI reference (at the time).
    # UPDATED (2026-07-17): `Milind Vijay Mokashi` (Designation
    # "Operations Manager") / `Sakshi Madan Agarwal` (Designation
    # "DGM - HR") were removed from the roster at the business owner's
    # direction -- neither Designation is shared by any other row, so
    # the distinct count drops by 2, 29 -> 27. This moves away from the
    # Power BI reference PDF's 29 (which predates today's roster edit),
    # expected, not a regression.
    df = load_roster(DEFAULT_ROSTER_PATH)
    assert get_departments(df) == 27


def test_get_data_quality_warnings_flags_designation_casing_mismatch():
    # RESOLVED AT SOURCE (2026-07-16): the real roster file's
    # "SalesForce Core Developer" rows were corrected to
    # "Salesforce Core Developer" directly in the source Excel file (see
    # backend/data/backups/ for the pre-fix backup), so this casing
    # duplicate no longer exists in the data and the warning correctly
    # no longer fires. The `_normalize_designation_label` normalization
    # and this warning check remain in place as a harmless safety net.
    df = load_roster(DEFAULT_ROSTER_PATH)
    warnings = get_data_quality_warnings(df)
    designation_warnings = [
        w for w in warnings if w["type"] == "designation_casing_mismatch"
    ]
    assert len(designation_warnings) == 0


# --------------------------------------------------------------------------
# Experience Band (PROVISIONAL)
# --------------------------------------------------------------------------


def test_experience_band_boundaries():
    assert _experience_band(0.5) == "0-1 Years"
    assert _experience_band(1.0) == "1-3 Years"  # half-open [1,3)
    assert _experience_band(2.99) == "1-3 Years"
    assert _experience_band(3.0) == "3-5 Years"
    assert _experience_band(5.0) == "5-8 Years"
    assert _experience_band(8.0) == "8+ Years"
    assert _experience_band(float("nan")) == "Unknown"


def test_get_workforce_by_experience_band(sample_roster):
    # E1=6.0->5-8, E2=0.5->0-1, E3=2.0->1-3, E4=4.0->3-5, E5=10.0->8+,
    # E6=NaN->Unknown
    assert get_workforce_by_experience_band(sample_roster) == {
        "0-1 Years": 1,
        "1-3 Years": 1,
        "3-5 Years": 1,
        "5-8 Years": 1,
        "8+ Years": 1,
        "Unknown": 1,
    }
    # Order matches EXPERIENCE_BAND_ORDER then "Unknown" last
    assert list(get_workforce_by_experience_band(sample_roster).keys()) == [
        "0-1 Years",
        "1-3 Years",
        "3-5 Years",
        "5-8 Years",
        "8+ Years",
        "Unknown",
    ]


# --------------------------------------------------------------------------
# Seniority Category (PROVISIONAL)
# --------------------------------------------------------------------------


def test_seniority_category_mapping():
    assert _seniority_category("Standard Senior") == "Senior"
    assert _seniority_category("Standard senior") == "Senior"
    assert _seniority_category("Standard Lead") == "Lead"
    assert _seniority_category("Premium lead") == "Lead"
    assert _seniority_category("Standard Mid") == "Mid"
    assert _seniority_category("Seniority TBD") == "TBD"
    assert _seniority_category("Hexa Sr") == "Senior"
    assert _seniority_category("Premium Technical Service Delivery Manager") == "Other"
    assert _seniority_category(float("nan")) == "Unknown"


def test_get_workforce_by_seniority_category(sample_roster):
    # SCOPE (2026-07-22): current workforce only — Active + Strategic Pool.
    # E3 (Mid) and E4 (TBD) are Inactive and so are excluded; a chart
    # titled "Workforce" must describe the same people as the other
    # workforce cards on the page.
    # Remaining: E1 Senior, E2 Lead, E5 Senior, E6 Other.
    assert get_workforce_by_seniority_category(sample_roster) == {
        "Senior": 2,
        "Lead": 1,
        "Other": 1,
    }


# --------------------------------------------------------------------------
# Trends across Available Months
# --------------------------------------------------------------------------


def test_get_month_wise_closing_headcount(sample_roster):
    # Available Months range from calendar.build_available_months:
    # DOJ (DEPT) min = 2025-01-01 (E3,E4), Today=2026-06-30 is the latest
    # candidate -> months Jan 2025..Jun 2026.
    result = get_month_wise_closing_headcount(sample_roster)
    months = [r["month"] for r in result]
    assert months[0] == "Jan 2025"
    assert months[-1] == "Jun 2026"
    # Jun 2026 Closing Headcount: DOJ<=2026-06-30 & (LWD blank | LWD>2026-06-30):
    #   E1 counted, E2 counted, E3 LWD=10-Mar-26 not >EndDate -> excluded,
    #   E4 LWD=5-Apr-26 -> excluded, E5 counted,
    #   E6 DOJ blank (true NaN) & LWD blank -> FIXED (2026-07-16, DAX
    #     BLANK() semantics bug): blank DOJ (DEPT) behaves like epoch-zero
    #     in DAX, so it's always <= EndDate -- E6 now counted (previously
    #     wrongly excluded by pandas' NaT-always-False comparison)
    # -> 4
    last = next(r for r in result if r["month"] == "Jun 2026")
    assert last["closing_headcount"] == 4


def test_get_monthly_joiners_vs_leavers(sample_roster):
    result = get_monthly_joiners_vs_leavers(sample_roster)
    by_month = {r["month"]: r for r in result}
    # Jan 2025: E3,E4,E5 all have DOJ (DEPT)=1-Jan-25 -> joiners=3
    assert by_month["Jan 2025"]["joiners"] == 3
    # Mar 2026: E3 exits -> exits=1
    assert by_month["Mar 2026"]["exits"] == 1
    # Apr 2026: E4 exits -> exits=1
    assert by_month["Apr 2026"]["exits"] == 1
    # Feb 2026: E2 joins -> joiners=1
    assert by_month["Feb 2026"]["joiners"] == 1


def test_get_month_wise_resignation_matches_exits(sample_roster):
    joiners_vs_leavers = get_monthly_joiners_vs_leavers(sample_roster)
    resignation = get_month_wise_resignation(sample_roster)
    assert [r["exits"] for r in resignation] == [r["exits"] for r in joiners_vs_leavers]
    assert all("joiners" not in r for r in resignation)


def test_get_voluntary_involuntary_split(sample_roster):
    # E3 Voluntary, E4 Involuntary
    assert get_voluntary_involuntary_split(sample_roster) == {
        "Voluntary": 1,
        "Involuntary": 1,
    }


# --------------------------------------------------------------------------
# Exits table
# --------------------------------------------------------------------------


def test_get_exits_table(sample_roster):
    table = get_exits_table(sample_roster)
    assert len(table) == 2
    names = {row["name"] for row in table}
    assert names == {"Cara Diaz", "Dev Patel"}
    cara = next(row for row in table if row["name"] == "Cara Diaz")
    assert cara == {
        "name": "Cara Diaz",
        "designation": "QA Lead",
        "primary_skill": "QA",
        "region": "EMEA",
        "market": "DACH",
        "type": "GCC",
        "lwd": "10-Mar-26",
        "reason_for_leaving": "Voluntary",
        "status": "Inactive",
    }


# --------------------------------------------------------------------------
# Skill bifurcation cross-tabs
# --------------------------------------------------------------------------


def test_get_skill_bifurcation_by_region(sample_roster):
    rows = get_skill_bifurcation_by_region(sample_roster)
    # E1 Front End/EMEA, E2 Front End/AMER, E3 QA/EMEA, E4 QA/AMER,
    # E5 Salesforce/EMEA, E6 Salesforce/None -> None dropped by groupby
    lookup = {(r["primary_skill"], r["region"]): r["count"] for r in rows}
    assert lookup[("Front End", "EMEA")] == 1
    assert lookup[("Front End", "AMER")] == 1
    assert lookup[("QA", "EMEA")] == 1
    assert lookup[("QA", "AMER")] == 1
    assert lookup[("Salesforce", "EMEA")] == 1
    assert ("Salesforce", None) not in lookup


def test_get_skill_bifurcation_by_experience_band(sample_roster):
    rows = get_skill_bifurcation_by_experience_band(sample_roster)
    lookup = {(r["primary_skill"], r["experience_band"]): r["count"] for r in rows}
    # E1 Front End/5-8, E2 Front End/0-1
    assert lookup[("Front End", "5-8 Years")] == 1
    assert lookup[("Front End", "0-1 Years")] == 1


def test_get_skill_bifurcation_by_seniority_category(sample_roster):
    rows = get_skill_bifurcation_by_seniority_category(sample_roster)
    lookup = {(r["primary_skill"], r["seniority_category"]): r["count"] for r in rows}
    # E1 Front End/Senior, E2 Front End/Lead
    assert lookup[("Front End", "Senior")] == 1
    assert lookup[("Front End", "Lead")] == 1


def test_get_workforce_details_by_region(sample_roster):
    rows = get_workforce_details_by_region(sample_roster)
    lookup = {(r["region"], r["seniority_category"]): r["count"] for r in rows}
    # E1 EMEA/Senior, E3 EMEA/Mid, E5 EMEA/Senior -> EMEA/Senior = 2
    assert lookup[("EMEA", "Senior")] == 2
    assert lookup[("EMEA", "Mid")] == 1
    # E2 AMER/Lead, E4 AMER/TBD
    assert lookup[("AMER", "Lead")] == 1
    assert lookup[("AMER", "TBD")] == 1


# --------------------------------------------------------------------------
# Employee Directory
# --------------------------------------------------------------------------


def test_get_employee_directory(sample_roster):
    directory = get_employee_directory(sample_roster)
    assert len(directory) == 6
    alice = next(r for r in directory if r["employee_id"] == "E1")
    # NAME "Alice  Smith" (double space) trimmed to "Alice Smith";
    # SUPERVISOR (Hexaware) "Bob  Jones" trimmed to "Bob Jones"
    assert alice["name"] == "Alice Smith"
    assert alice["supervisor"] == "Bob Jones"
    assert alice["grade"] == "G5"
    assert alice["region"] == "EMEA"
    assert alice["seniority_level"] == "Standard Senior"
    assert alice["client"] == "Acme Corp"


# --------------------------------------------------------------------------
# Regression tests against the real roster file
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_roster() -> pd.DataFrame:
    if not (FIXTURES_DIR / "roster_snapshot.xlsx").exists():
        pytest.skip(f"real roster file not present at {DEFAULT_ROSTER_PATH}")
    # Loaded through the SAME path the dashboard uses — the ingestion
    # contract's defaults applied (blank experience -> 0, blank employee id
    # -> "NEW_EMP_ID TBD n"). Reading the file raw here would measure
    # different data than the app actually shows: a blank NEW_EMP_ID is
    # dropped by nunique(), so raw reads report 33 active where the
    # dashboard reports 35.
    return apply_dataset_defaults(load_roster(FIXTURES_DIR / "roster_snapshot.xlsx"), "roster")


def test_real_roster_headcount_by_region_matches_reference(real_roster):
    # Matched the reference PDF's reported breakdown exactly (at the
    # time): 32 EMEA / 15 AMER / 2 Hexaware / 2 Region TBD / 1 APAC.
    # UPDATED (2026-07-17): `Milind Vijay Mokashi` / `Sakshi Madan
    # Agarwal` were both `Region` "Hexaware" (internal corporate staff)
    # -- removing them at the business owner's direction drops that
    # bucket to 0, which no longer appears as a key at all (the
    # underlying groupby only returns buckets with at least 1 row).
    # Every other region is unaffected.
    assert get_headcount_by_region(real_roster) == {
        "EMEA": 32,
        "AMER": 15,
        "Region TBD": 2,
        "APAC": 1,
    }


def test_real_roster_status_split(real_roster):
    # UPDATED (2026-07-17, two changes same day): the 2 blank-DOJ(DEPT)
    # employees are now Status "Strategic Pool" instead of "Active", and
    # `Milind Vijay Mokashi` / `Sakshi Madan Agarwal` (both Status
    # "Active") were removed from the roster entirely -- see
    # test_real_roster_headcount in test_roster_metrics.py.
    assert get_status_split(real_roster) == {
        "Active": 43,
        "Inactive": 5,
        "Strategic Pool": 2,
    }


def test_real_roster_workforce_by_type(real_roster):
    # UPDATED (2026-07-17): `Milind Vijay Mokashi` / `Sakshi Madan
    # Agarwal` removed from the roster -- one was `Type` "GCC" (48->47),
    # the other "Non GCC" (4->3).
    assert get_workforce_by_type(real_roster) == {"GCC": 47, "Non GCC": 3}


def test_real_roster_strategic_pool(real_roster):
    # FIXED (2026-07-16, DAX BLANK() semantics bug): ISBLANK(DOJ (DEPT))
    # must be evaluated against the PARSED date column, not the raw
    # string column -- a Date-typed column in the Power BI model treats
    # an unparseable literal like "TBD" as BLANK() at import time, so the
    # correct pandas equivalent is `_parse_dept_dates(df).isna()`
    # (NaT), which correctly catches both TBD rows (NEW_EMP_ID
    # 2000194634, 2000195658) -> 2, matching the Power BI reference.
    # Previously wrongly checked the raw string column (`"TBD" != NaN`),
    # giving 0.
    assert get_strategic_pool(real_roster) == 2


def test_real_roster_working_entity(real_roster):
    # Computed via df['Working Entity'].value_counts() on the real file.
    # UPDATED (2026-07-17): `Milind Vijay Mokashi` / `Sakshi Madan
    # Agarwal` were both `Working Entity` "Hexaware" -- removing them at
    # the business owner's direction drops that bucket to 0, which no
    # longer appears as a key (same pattern as the region breakdown
    # above). Every other entity is unaffected.
    assert get_workforce_by_working_entity(real_roster) == {
        "AMER": 15,
        "DTNL": 14,
        "DTIE": 12,
        "DTDE": 4,
        "DTUK": 2,
        "Entity TBD": 2,
        "DTAU": 1,
    }


def test_real_roster_experience_band(real_roster):
    # Computed via the provisional bucketing over Total Experience.
    # UPDATED (2026-07-17): `Milind Vijay Mokashi` / `Sakshi Madan
    # Agarwal` removed from the roster -- one was in the "0-1 Years"
    # band (6->5), the other was the ONLY row in "1-3 Years" (1->0,
    # bucket is empty). UPDATED (2026-07-22): every declared band is now
    # always returned, in declared order, even at zero — an empty band
    # should render as a zero bar rather than silently disappearing from
    # the axis (and the axis order was previously arbitrary).
    assert get_workforce_by_experience_band(real_roster) == {
        "0-1 Years": 5,
        "1-3 Years": 0,
        "3-5 Years": 2,
        "5-8 Years": 12,
        "8+ Years": 31,
    }
    assert list(get_workforce_by_experience_band(real_roster)) == [
        "0-1 Years",
        "1-3 Years",
        "3-5 Years",
        "5-8 Years",
        "8+ Years",
    ]


def test_real_roster_headcount_by_seniority_collapses_casing(real_roster):
    # Confirmed real-file raw counts before collapsing: "Premium Lead" (1)
    # + "Premium lead" (5) = 6; "Standard Senior" (8) + "Standard senior"
    # (1) = 9. All other Seniorirty Level values in the real file have no
    # casing duplicate, so they pass through unchanged (title-cased).
    result = get_headcount_by_seniority(real_roster)
    assert result["Premium Lead"] == 6
    assert result["Standard Senior"] == 9
    assert "Premium lead" not in result
    assert "Standard senior" not in result


def test_real_roster_seniority_category(real_roster):
    # UPDATED (2026-07-17): `Milind Vijay Mokashi` / `Sakshi Madan
    # Agarwal` (Designations "Operations Manager" / "DGM - HR") were both
    # in the "Senior" seniority category -- removing them at the business
    # owner's direction drops that bucket 19->17. Every other category
    # unaffected.
    # SCOPE (2026-07-22): current workforce only (Active + Strategic Pool
    # = 45 of the snapshot's 50 rows), so the 5 Inactive employees are no
    # longer counted. All 5 sat in the TBD bucket, which drops 7 -> 2;
    # every other band is unchanged.
    assert get_workforce_by_seniority_category(real_roster) == {
        "Lead": 18,
        "Senior": 17,
        "Mid": 7,
        "TBD": 2,
        "Other": 1,
    }
    assert sum(get_workforce_by_seniority_category(real_roster).values()) == 45


def test_real_roster_month_wise_closing_headcount(real_roster):
    result = get_month_wise_closing_headcount(real_roster)
    assert result[0]["month"] == "Jul 2025"
    assert result[-1]["month"] == "Jun 2026"
    # Jun 2026 Closing Headcount matches get_closing_headcount's own
    # regression test value. UPDATED (2026-07-17): was 47, now 45 -- see
    # test_roster_metrics.py's
    # test_real_roster_date_based_headcount_explicit_june_2026 for the
    # full accounting (Milind Vijay Mokashi / Sakshi Madan Agarwal both
    # counted in June's Closing Headcount before being removed).
    assert result[-1]["closing_headcount"] == 45


def test_real_roster_exits_table_count(real_roster):
    # 5 Inactive rows all have LWD populated (per data-model SKILL.md's
    # "LWD only populated when Status = Inactive" rule) -> 5 rows.
    table = get_exits_table(real_roster)
    assert len(table) == 5
    assert all(row["status"] == "Inactive" for row in table)


def test_real_roster_employee_directory_count(real_roster):
    # UPDATED (2026-07-17): `Milind Vijay Mokashi` / `Sakshi Madan
    # Agarwal` removed from the roster at the business owner's direction
    # -- see test_real_roster_headcount in test_roster_metrics.py.
    directory = get_employee_directory(real_roster)
    assert len(directory) == 50
    assert all("  " not in (r["name"] or "") for r in directory)


# --------------------------------------------------------------------------
# Card declarations must actually DRIVE the numbers, not just describe them
# --------------------------------------------------------------------------


def test_cards_are_driven_by_their_yaml_declaration(tmp_path, monkeypatch):
    """
    The `cards:` block in roster_metrics.yaml is the definition of record.
    A declaration that merely *describes* the code is worse than none —
    it reads as authoritative while changing it does nothing. This asserts
    editing the declaration really does change the number.
    """
    import yaml

    from app.services import metric_config
    from app.services.roster_metrics import get_projects, get_total_employees
    from app.services.validation.engine import prepare_dataset

    cfg_path = (
        Path(metric_config.__file__).resolve().parent
        / "configs"
        / "roster_metrics.yaml"
    )
    original = cfg_path.read_text()

    def fresh():
        # a new frame each time, so @cache_on_df can't serve a stale result
        return prepare_dataset(
            load_roster(FIXTURES_DIR / "roster_snapshot.xlsx"), "roster"
        )

    assert get_projects(fresh()) == 31
    assert get_total_employees(fresh()) == 50

    try:
        cfg = yaml.safe_load(original)
        cfg["cards"]["projects"]["column_role"] = "designation"
        cfg["cards"]["total_employees"]["status_filter"] = "inactive"
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
        metric_config.load_metric_config.cache_clear()

        assert get_projects(fresh()) == 27       # now counts job titles
        assert get_total_employees(fresh()) == 5  # now Inactive only
    finally:
        cfg_path.write_text(original)
        metric_config.load_metric_config.cache_clear()

    assert get_projects(fresh()) == 31
    assert get_total_employees(fresh()) == 50
