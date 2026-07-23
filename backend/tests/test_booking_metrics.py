"""
Tests for backend/app/services/booking_metrics.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.services.validation.engine import apply_dataset_defaults

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

from app.services.booking_metrics import (
    DEFAULT_BOOKING_PATH,
    get_client_hours,
    get_client_hours_pct,
    get_employee_detail,
    get_filter_options,
    get_filtered_records,
    get_holdings_with_projects,
    get_hours_by_region,
    get_hours_by_region_market,
    get_internal_hours,
    get_internal_hours_pct,
    get_markets_covered,
    get_project_detail,
    get_records_summary,
    get_total_clients,
    get_total_employees,
    get_total_hours,
    get_total_projects,
    get_total_regions,
    get_weekly_hours_trend,
    load_booking_data,
    records_to_dicts,
)


@pytest.fixture
def sample_bookings() -> pd.DataFrame:
    """
    6 hand-built rows across 3 employees, 2 distinct Holdings (clients),
    3 distinct Project Names, mixed Client/Internal hours.
    """
    return pd.DataFrame(
        [
            {
                "Employee": "Alice",
                "Holding": "Acme Corp",
                "Project Name": "Acme Website",
                "Booked Hours Type": "Client Hours",
                "Employee Booked Hours": 20.0,
                "Region (EC)": "EMEA",
                "Market (EC)": "UKI",
            },
            {
                "Employee": "Alice",
                "Holding": "Acme Corp",
                "Project Name": "Acme Website",
                "Booked Hours Type": "Internal Hours",
                "Employee Booked Hours": 5.0,
                "Region (EC)": "EMEA",
                "Market (EC)": "UKI",
            },
            {
                "Employee": "Bob",
                "Holding": "Beta Inc",
                "Project Name": "Beta App",
                "Booked Hours Type": "Client Hours",
                "Employee Booked Hours": 15.0,
                "Region (EC)": "AMER",
                "Market (EC)": "AMER",
            },
            {
                "Employee": "Bob",
                "Holding": "Beta Inc",
                "Project Name": "Beta Migration",
                "Booked Hours Type": "Client Hours",
                "Employee Booked Hours": 10.0,
                "Region (EC)": "AMER",
                "Market (EC)": "AMER",
            },
            {
                "Employee": "Carol",
                "Holding": "Beta Inc",
                "Project Name": "Beta App",
                "Booked Hours Type": "Internal Hours",
                "Employee Booked Hours": 8.0,
                "Region (EC)": "EMEA",
                "Market (EC)": "DACH",
            },
            {
                "Employee": "Carol",
                "Holding": None,  # unallocated row, should not count as a client
                "Project Name": None,
                "Booked Hours Type": "Internal Hours",
                "Employee Booked Hours": 2.0,
                "Region (EC)": None,
                "Market (EC)": None,
            },
        ]
    )


def test_get_total_hours(sample_bookings):
    # 20 + 5 + 15 + 10 + 8 + 2 = 60
    assert get_total_hours(sample_bookings) == pytest.approx(60.0)


def test_get_client_hours(sample_bookings):
    # 20 + 15 + 10 = 45
    assert get_client_hours(sample_bookings) == pytest.approx(45.0)


def test_get_internal_hours(sample_bookings):
    # 5 + 8 + 2 = 15
    assert get_internal_hours(sample_bookings) == pytest.approx(15.0)


def test_get_client_hours_pct(sample_bookings):
    # 45 / 60 * 100 = 75.0
    assert get_client_hours_pct(sample_bookings) == pytest.approx(75.0)


def test_get_internal_hours_pct(sample_bookings):
    # 15 / 60 * 100 = 25.0
    assert get_internal_hours_pct(sample_bookings) == pytest.approx(25.0)


def test_get_client_hours_pct_zero_total():
    df = pd.DataFrame(columns=["Booked Hours Type", "Employee Booked Hours"])
    assert get_client_hours_pct(df) == 0.0


def test_get_total_clients(sample_bookings):
    # distinct Holding excluding NaN: Acme Corp, Beta Inc -> 2
    assert get_total_clients(sample_bookings) == 2


def test_get_total_projects(sample_bookings):
    # distinct Project Name excluding NaN: Acme Website, Beta App, Beta Migration -> 3
    # (implements Sheet1[Project] from the DAX -- resolved to this file's
    # `Project Name` column, see get_total_projects docstring)
    assert get_total_projects(sample_bookings) == 3


def test_get_total_regions(sample_bookings):
    # distinct Region (EC) excluding NaN: EMEA, AMER -> 2
    assert get_total_regions(sample_bookings) == 2


def test_get_markets_covered(sample_bookings):
    # distinct Market (EC) excluding NaN: UKI, AMER, DACH -> 3
    assert get_markets_covered(sample_bookings) == 3


@pytest.fixture
def sample_bookings_full() -> pd.DataFrame:
    """
    5 hand-built rows across 3 employees, 2 Holdings, 2 weeks, adding the
    Department/Team (EC)/Monday of Week/Date columns needed by the
    Search-page filter/detail functions.
    """
    return pd.DataFrame(
        [
            {
                "Employee": "Alice", "Holding": "Acme Corp", "Project Name": "Acme Website",
                "Booked Hours Type": "Client Hours", "Employee Booked Hours": 20.0,
                "Region (EC)": "EMEA", "Market (EC)": "UKI", "Department": "Engineering",
                "Team (EC)": "T1", "Monday of Week": "2026-05-04", "Date": "2026-05-04", "Month": "May 26",
            },
            {
                "Employee": "Alice", "Holding": "Acme Corp", "Project Name": "Acme Website",
                "Booked Hours Type": "Internal Hours", "Employee Booked Hours": 5.0,
                "Region (EC)": "EMEA", "Market (EC)": "UKI", "Department": "Engineering",
                "Team (EC)": "T1", "Monday of Week": "2026-05-04", "Date": "2026-05-05", "Month": "May 26",
            },
            {
                "Employee": "Bob", "Holding": "Beta Inc", "Project Name": "Beta App",
                "Booked Hours Type": "Client Hours", "Employee Booked Hours": 15.0,
                "Region (EC)": "AMER", "Market (EC)": "AMER", "Department": "QA",
                "Team (EC)": "T2", "Monday of Week": "2026-05-04", "Date": "2026-05-04", "Month": "May 26",
            },
            {
                "Employee": "Bob", "Holding": "Beta Inc", "Project Name": "Beta Migration",
                "Booked Hours Type": "Client Hours", "Employee Booked Hours": 10.0,
                "Region (EC)": "AMER", "Market (EC)": "AMER", "Department": "QA",
                "Team (EC)": "T2", "Monday of Week": "2026-05-11", "Date": "2026-05-11", "Month": "May 26",
            },
            {
                "Employee": "Carol", "Holding": "Beta Inc", "Project Name": "Beta App",
                "Booked Hours Type": "Internal Hours", "Employee Booked Hours": 8.0,
                "Region (EC)": "EMEA", "Market (EC)": "DACH", "Department": "Engineering",
                "Team (EC)": "T1", "Monday of Week": "2026-05-11", "Date": "2026-05-12", "Month": "May 26",
            },
        ]
    )


def test_get_total_employees(sample_bookings_full):
    # distinct Employee: Alice, Bob, Carol -> 3
    assert get_total_employees(sample_bookings_full) == 3


def test_get_weekly_hours_trend(sample_bookings_full):
    # 2026-05-04: client 20+15=35, internal 5; 2026-05-11: client 10, internal 8
    trend = get_weekly_hours_trend(sample_bookings_full)
    by_week = {row["week_start"]: row for row in trend}
    assert by_week["2026-05-04"]["client_hours"] == pytest.approx(35.0)
    assert by_week["2026-05-04"]["internal_hours"] == pytest.approx(5.0)
    assert by_week["2026-05-11"]["client_hours"] == pytest.approx(10.0)
    assert by_week["2026-05-11"]["internal_hours"] == pytest.approx(8.0)


def test_get_hours_by_region(sample_bookings_full):
    # EMEA: 20+5+8=33, AMER: 15+10=25, sorted descending
    result = get_hours_by_region(sample_bookings_full)
    assert result[0] == {"region": "EMEA", "total_hours": pytest.approx(33.0)}
    assert result[1] == {"region": "AMER", "total_hours": pytest.approx(25.0)}


def test_get_hours_by_region_market(sample_bookings_full):
    # EMEA/UKI: 20+5=25, AMER/AMER: 15+10=25, EMEA/DACH: 8, sorted descending
    # (ties between EMEA/UKI and AMER/AMER broken by groupby's stable
    # lexicographic key order: AMER sorts before EMEA)
    result = get_hours_by_region_market(sample_bookings_full)
    by_pair = {(r["region"], r["market"]): r["total_hours"] for r in result}
    assert by_pair[("EMEA", "UKI")] == pytest.approx(25.0)
    assert by_pair[("AMER", "AMER")] == pytest.approx(25.0)
    assert by_pair[("EMEA", "DACH")] == pytest.approx(8.0)
    assert len(result) == 3


def test_get_filter_options(sample_bookings_full):
    opts = get_filter_options(sample_bookings_full)
    assert opts["weeks"] == ["2026-05-04", "2026-05-11"]
    assert opts["regions"] == ["AMER", "EMEA"]
    assert opts["markets"] == ["AMER", "DACH", "UKI"]
    assert opts["departments"] == ["Engineering", "QA"]
    assert opts["entities"] == ["T1", "T2"]
    assert opts["holdings"] == ["Acme Corp", "Beta Inc"]
    assert opts["hours_types"] == ["Client Hours", "Internal Hours"]
    # Year > Month > Week hierarchy for the cascading date filter: one entry
    # per distinct week, each carrying its year (from the Monday) and its
    # booking-sheet Month label.
    assert opts["week_hierarchy"] == [
        {"year": "2026", "month": "May 26", "week": "2026-05-04"},
        {"year": "2026", "month": "May 26", "week": "2026-05-11"},
    ]


def test_get_filtered_records_market_filter(sample_bookings_full):
    # market alone -> UKI: Alice's 2 rows
    assert len(get_filtered_records(sample_bookings_full, market="UKI")) == 2
    # market=AMER AND hours_type=Client Hours -> Bob's 2 rows
    result = get_filtered_records(sample_bookings_full, market="AMER", hours_type="Client Hours")
    assert len(result) == 2


def test_get_filtered_records_multi_value_or_within_field(sample_bookings_full):
    # region IN (EMEA, AMER) -> all 5 rows (both regions present)
    assert len(get_filtered_records(sample_bookings_full, region=["EMEA", "AMER"])) == 5
    # region IN (EMEA) alone via list -> same as single-string form (3 rows)
    assert len(get_filtered_records(sample_bookings_full, region=["EMEA"])) == len(
        get_filtered_records(sample_bookings_full, region="EMEA")
    )
    # holding IN (Acme Corp, Beta Inc) AND hours_type IN (Client Hours)
    # -> Alice's client row + Bob's 2 client rows = 3 (OR within holding, AND across fields)
    result = get_filtered_records(
        sample_bookings_full,
        holding=["Acme Corp", "Beta Inc"],
        hours_type=["Client Hours"],
    )
    assert len(result) == 3
    # empty list behaves as no-op, same as None
    assert len(get_filtered_records(sample_bookings_full, region=[])) == 5


def test_get_holdings_with_projects(sample_bookings_full):
    items = get_holdings_with_projects(sample_bookings_full)
    by_holding = {item["holding"]: item["projects"] for item in items}
    assert by_holding["Acme Corp"] == ["Acme Website"]
    assert by_holding["Beta Inc"] == ["Beta App", "Beta Migration"]
    assert [item["holding"] for item in items] == ["Acme Corp", "Beta Inc"]


def test_get_filtered_records_single_filters(sample_bookings_full):
    # week alone -> 3 rows logged the week of 2026-05-04 (Alice x2, Bob x1)
    assert len(get_filtered_records(sample_bookings_full, week="2026-05-04")) == 3
    # region alone -> EMEA: Alice x2 + Carol x1 = 3
    assert len(get_filtered_records(sample_bookings_full, region="EMEA")) == 3
    # department alone -> QA: Bob x2 = 2
    assert len(get_filtered_records(sample_bookings_full, department="QA")) == 2
    # entity alone -> T1: Alice x2 + Carol x1 = 3
    assert len(get_filtered_records(sample_bookings_full, entity="T1")) == 3
    # holding alone -> Beta Inc: Bob x2 + Carol x1 = 3
    assert len(get_filtered_records(sample_bookings_full, holding="Beta Inc")) == 3
    # hours_type alone -> Client Hours: Alice x1 + Bob x2 = 3
    assert len(get_filtered_records(sample_bookings_full, hours_type="Client Hours")) == 3


def test_get_filtered_records_combines_with_and(sample_bookings_full):
    # region=EMEA AND hours_type=Client Hours -> only Alice's client row -> 1
    # (if this were OR'd instead, it would include Carol's internal EMEA row
    # and Bob's client AMER rows, giving a much larger count)
    result = get_filtered_records(
        sample_bookings_full, region="EMEA", hours_type="Client Hours"
    )
    assert len(result) == 1
    assert result.iloc[0]["Employee"] == "Alice"

    # region=AMER AND department=QA -> Bob's 2 rows
    result2 = get_filtered_records(sample_bookings_full, region="AMER", department="QA")
    assert len(result2) == 2

    # region=EMEA AND department=QA -> no rows have both -> 0 (proves AND, not OR)
    result3 = get_filtered_records(sample_bookings_full, region="EMEA", department="QA")
    assert len(result3) == 0


def test_get_records_summary(sample_bookings_full):
    filtered = get_filtered_records(sample_bookings_full, holding="Beta Inc")
    summary = get_records_summary(filtered)
    # Bob(15+10) + Carol(8) = 33 total, 25 client, 8 internal
    assert summary["total_hours"] == pytest.approx(33.0)
    assert summary["client_hours"] == pytest.approx(25.0)
    assert summary["internal_hours"] == pytest.approx(8.0)
    # distinct Project Name among these 3 rows: Beta App, Beta Migration -> 2
    assert summary["total_projects"] == 2
    # 33 / 3 rows = 11.0
    assert summary["average_hours"] == pytest.approx(11.0)


def test_get_records_summary_empty():
    empty = pd.DataFrame(columns=["Booked Hours Type", "Employee Booked Hours", "Project Name"])
    summary = get_records_summary(empty)
    assert summary["total_hours"] == 0.0
    assert summary["average_hours"] == 0.0


def test_records_to_dicts(sample_bookings_full):
    records = records_to_dicts(sample_bookings_full.iloc[[0]])
    assert records == [
        {
            "week_start": "2026-05-04",
            "date": "2026-05-04",
            "employee": "Alice",
            "project": "Acme Website",
            "holding": "Acme Corp",
            "hours_type": "Client Hours",
            "hours": 20.0,
            "region": "EMEA",
            "department": "Engineering",
            "team": "T1",
        }
    ]


def test_get_employee_detail_found(sample_bookings_full):
    detail = get_employee_detail(sample_bookings_full, "Alice")
    assert detail["total_hours"] == pytest.approx(25.0)
    assert detail["client_hours"] == pytest.approx(20.0)
    assert detail["internal_hours"] == pytest.approx(5.0)
    assert detail["total_projects"] == 1
    assert detail["hours_by_project"] == [{"project": "Acme Website", "total_hours": pytest.approx(25.0)}]


def test_get_employee_detail_not_found_returns_none(sample_bookings_full):
    # unknown employee -> None, which the API layer (utilization.py) turns
    # into a 404, not an exception
    assert get_employee_detail(sample_bookings_full, "Nobody Here") is None


def test_get_project_detail_found(sample_bookings_full):
    detail = get_project_detail(sample_bookings_full, "Beta Inc")
    assert detail["total_hours"] == pytest.approx(33.0)
    assert detail["client_hours"] == pytest.approx(25.0)
    assert detail["internal_hours"] == pytest.approx(8.0)
    by_employee = {row["employee"]: row for row in detail["hours_by_employee"]}
    assert by_employee["Bob"]["client_hours"] == pytest.approx(25.0)
    assert by_employee["Carol"]["internal_hours"] == pytest.approx(8.0)
    assert len(detail["detail"]) == 3


def test_get_project_detail_not_found_returns_none(sample_bookings_full):
    # unknown holding -> None, which the API layer 404s on
    assert get_project_detail(sample_bookings_full, "Nonexistent Holding XYZ") is None


# --------------------------------------------------------------------------
# Regression tests against the real booking sheet
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_bookings() -> pd.DataFrame:
    if not (FIXTURES_DIR / "booking_snapshot.xlsx").exists():
        pytest.skip(f"real booking file not present at {DEFAULT_BOOKING_PATH}")
    # Loaded through the SAME path the dashboard uses — the ingestion
    # contract's defaults applied (blank experience -> 0, blank employee id
    # -> "NEW_EMP_ID TBD n"). Reading the file raw here would measure
    # different data than the app actually shows: a blank NEW_EMP_ID is
    # dropped by nunique(), so raw reads report 33 active where the
    # dashboard reports 35.
    return apply_dataset_defaults(load_booking_data(FIXTURES_DIR / "booking_snapshot.xlsx"), "booking")


def test_real_bookings_hours(real_bookings):
    # REGRESSION VALUES UPDATED 2026-07-15: the source file was replaced
    # (258 rows / 2 weeks -> 1523 rows / 7 weeks, 2026-04-13 .. 2026-05-25).
    # Recomputed via: df['Employee Booked Hours'].sum() == 8928.6 (note:
    # the raw file has 1523 rows but 1 row is fully blank/NaN across every
    # column -- pandas .sum() naturally excludes the NaN hours value from
    # this row, so it does not affect the total; see
    # get_data_quality_warnings-style handling note in load_booking_data).
    assert get_total_hours(real_bookings) == pytest.approx(8928.6, abs=0.01)
    # Client Hours rows sum == 6467.7, Internal Hours rows sum == 2460.9
    assert get_client_hours(real_bookings) == pytest.approx(6467.7, abs=0.01)
    assert get_internal_hours(real_bookings) == pytest.approx(2460.9, abs=0.01)


def test_real_bookings_hours_pct(real_bookings):
    # REGRESSION VALUES UPDATED 2026-07-15 (see test_real_bookings_hours).
    # 6467.7 / 8928.6 * 100 = 72.4380
    assert get_client_hours_pct(real_bookings) == pytest.approx(72.4380, abs=0.01)
    # 2460.9 / 8928.6 * 100 = 27.5620
    assert get_internal_hours_pct(real_bookings) == pytest.approx(27.5620, abs=0.01)


def test_real_bookings_scope(real_bookings):
    # REGRESSION VALUES UPDATED 2026-07-15 (see test_real_bookings_hours).
    # df['Holding'].nunique() == 43, df['Project Name'].nunique() == 66
    assert get_total_clients(real_bookings) == 43
    assert get_total_projects(real_bookings) == 66
    # df['Region (EC)'].nunique() == 2, df['Market (EC)'].nunique() == 4
    assert get_total_regions(real_bookings) == 2
    assert get_markets_covered(real_bookings) == 4


def test_real_bookings_total_employees(real_bookings):
    # df['Employee'].nunique() == 46 (independently confirmed 2026-07-15)
    assert get_total_employees(real_bookings) == 46


def test_real_bookings_weekly_trend_and_region(real_bookings):
    # 7 distinct Monday of Week values in the file
    trend = get_weekly_hours_trend(real_bookings)
    assert len(trend) == 7
    # First week (2026-04-13) hand-verified: client=1290.8, internal=442.8
    assert trend[0]["week_start"] == "2026-04-13"
    assert trend[0]["client_hours"] == pytest.approx(1290.8, abs=0.01)
    assert trend[0]["internal_hours"] == pytest.approx(442.8, abs=0.01)

    by_region = get_hours_by_region(real_bookings)
    assert by_region[0] == {"region": "EMEA", "total_hours": pytest.approx(6218.6, abs=0.01)}
    assert by_region[1] == {"region": "AMER", "total_hours": pytest.approx(2710.0, abs=0.01)}


def test_real_bookings_hours_by_region_market(real_bookings):
    # UPDATED (2026-07-17): at the business owner's explicit direction,
    # `Market (EC)` values were corrected directly in the source Excel
    # file -- "BN" -> "BENO" and "Technology" -> "AMER" -- since those
    # were data-entry errors, not intentional labels (this resolves the
    # "unconfirmed/pending reconciliation" flag this test used to carry).
    # Hand-verified via df.groupby(['Region (EC)','Market (EC)'])
    # ['Employee Booked Hours'].sum() on the real file post-fix. Hours
    # totals per pair are unchanged (only the labels moved), matching
    # the reference chart's AMER/BENO/DACH/UKI labels exactly now.
    by_region_market = get_hours_by_region_market(real_bookings)
    by_pair = {(r["region"], r["market"]): r["total_hours"] for r in by_region_market}
    assert by_pair[("EMEA", "BENO")] == pytest.approx(3142.0, abs=0.01)
    assert by_pair[("AMER", "AMER")] == pytest.approx(2710.0, abs=0.01)
    assert by_pair[("EMEA", "UKI")] == pytest.approx(2099.6, abs=0.01)
    assert by_pair[("EMEA", "DACH")] == pytest.approx(977.0, abs=0.01)
    assert len(by_region_market) == 4
    assert sum(r["total_hours"] for r in by_region_market) == pytest.approx(8928.6, abs=0.01)


def test_real_bookings_filter_options(real_bookings):
    opts = get_filter_options(real_bookings)
    assert len(opts["weeks"]) == 7
    assert opts["regions"] == ["AMER", "EMEA"]
    # df['Market (EC)'].nunique() == 4, matches get_markets_covered.
    # UPDATED (2026-07-17): "BN"/"Technology" corrected to "BENO"/"AMER"
    # at source -- see test_real_bookings_hours_by_region_market.
    assert sorted(opts["markets"]) == ["AMER", "BENO", "DACH", "UKI"]
    assert len(opts["departments"]) == 7
    assert len(opts["entities"]) == 5
    assert len(opts["holdings"]) == 43
    assert opts["hours_types"] == ["Client Hours", "Internal Hours"]


def test_real_bookings_filtered_records_and(real_bookings):
    # single filter
    emea_only = get_filtered_records(real_bookings, region="EMEA")
    assert len(emea_only) == 994
    # combined filter must AND, giving a strict subset of the single-filter count
    emea_client = get_filtered_records(real_bookings, region="EMEA", hours_type="Client Hours")
    assert len(emea_client) == 698
    assert len(emea_client) < len(emea_only)


def test_real_bookings_filtered_records_multi_value(real_bookings):
    # region IN (EMEA, AMER) covers every real Region (EC) value in the
    # file, RESOLVED AT SOURCE (2026-07-17): the partial-blank row (only
    # `Project URL` populated, every other column NaN) that used to sit
    # at the end of the file was removed directly from
    # `UTILIZATION DATA SHEET.xlsx` (backup taken beforehand) -- see the
    # data-model skill. both_regions now equals the full row count.
    both_regions = get_filtered_records(real_bookings, region=["EMEA", "AMER"])
    assert len(both_regions) == len(real_bookings)
    # market IN (BN, DACH) -- OR within field
    by_market = get_filtered_records(real_bookings, market=["BN", "DACH"])
    assert len(by_market) == len(
        get_filtered_records(real_bookings, market="BN")
    ) + len(get_filtered_records(real_bookings, market="DACH"))
    # market IN (BN, DACH) AND hours_type IN (Client Hours) -- AND across fields
    combined = get_filtered_records(
        real_bookings, market=["BN", "DACH"], hours_type=["Client Hours"]
    )
    assert len(combined) < len(by_market)


def test_real_bookings_holdings_with_projects(real_bookings):
    items = get_holdings_with_projects(real_bookings)
    # matches get_total_clients == 43 distinct Holding values
    assert len(items) == 43
    by_holding = {item["holding"]: item["projects"] for item in items}
    # Arcadis GBV hand-verified single project, matches get_project_detail
    # real-file regression above (total_hours 528.0, all Client Hours)
    assert by_holding["Arcadis GBV"] == ["ARD26-88008 - Arcadis Website Launch"]


def test_real_bookings_employee_and_project_detail(real_bookings):
    detail = get_employee_detail(real_bookings, "Duddi Kumar")
    assert detail["total_hours"] == pytest.approx(234.0, abs=0.01)
    assert detail["client_hours"] == pytest.approx(179.0, abs=0.01)
    assert detail["internal_hours"] == pytest.approx(55.0, abs=0.01)
    assert detail["total_projects"] == 3
    assert get_employee_detail(real_bookings, "Definitely Not A Real Employee") is None

    project = get_project_detail(real_bookings, "Arcadis GBV")
    assert project["total_hours"] == pytest.approx(528.0, abs=0.01)
    assert project["client_hours"] == pytest.approx(528.0, abs=0.01)
    assert project["internal_hours"] == pytest.approx(0.0, abs=0.01)
    assert get_project_detail(real_bookings, "Definitely Not A Real Holding") is None


def test_real_bookings_records_to_dicts_includes_region_department_team(real_bookings):
    # Duddi Kumar's first row (2026-04-13): Region (EC)=AMER,
    # Department=Creative Content, Team (EC)=CMUS -- hand-verified against
    # the real source file.
    row = real_bookings[
        (real_bookings["Employee"] == "Duddi Kumar")
        & (pd.to_datetime(real_bookings["Date"]) == pd.Timestamp("2026-04-13"))
    ].iloc[[0]]
    records = records_to_dicts(row)
    assert records[0]["region"] == "AMER"
    assert records[0]["department"] == "Creative Content"
    assert records[0]["team"] == "CMUS"


def test_real_bookings_filtered_records_excludes_blank_row(real_bookings):
    # Regression for the ghost "--" row bug, RESOLVED AT SOURCE
    # (2026-07-16) for the *original* fully-blank row (previously at raw
    # index 258, deleted from the source file -- see load_booking_data
    # docstring / the data-model skill).
    #
    # RESOLVED AT SOURCE (2026-07-17): a DIFFERENT partial-blank row (only
    # `Project URL` populated, every other column including `Employee`
    # NaN) had appeared at the end of the file -- confirmed PRE-EXISTING
    # as of the backup taken before that day's edits. It has now been
    # deleted directly from `UTILIZATION DATA SHEET.xlsx` (backup taken
    # first) rather than carried forward as an open item -- see the
    # data-model skill. Every row now has a non-null `Employee`.
    unfiltered = get_filtered_records(real_bookings)
    assert len(unfiltered) == len(real_bookings)
    assert len(unfiltered) == 1522
    assert unfiltered["Employee"].isna().sum() == 0

    # records_to_dicts passes every row through unchanged.
    records = records_to_dicts(unfiltered)
    assert len(records) == 1522
    assert sum(1 for r in records if r["employee"] is None) == 0
