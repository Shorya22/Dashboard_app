"""TEMPORARY demo-only KPI overrides — DELETE BEFORE MERGING.

Exists solely to display a fixed set of headline numbers during a
manager-requested demo on the `feature/temp` branch. These values are
NOT computed from the roster and do NOT agree with
`backend/data/DEPT - Master Data(Sheet1).xlsx`.

Removal is one step: delete this file and the three `demo_overrides.apply_*`
calls in `app/api/roster.py`.

Requested vs. real (as computed from the current roster file):

    measure              demo    real
    Active Employees       35      33
    Inactive Employees      8      14
    Total Employees        55      50
    Strategic Pool          3       3
    Closing Headcount      38      45
    Exits                   9       5

Everything below those six is derived so the screen doesn't contradict
itself. The reconciling identity (confirmed with the requester) is:

    Total 55 = Active 35 + Inactive 8 + Strategic Pool 3 + Exited 9
    Closing Headcount 38 = Active 35 + Strategic Pool 3
    Opening 2 + Joiners 45 - Exits 9 = Closing 38

so `joiners` moves 48 -> 45 to keep that identity true, and every
category breakdown is padded from its real shape to total 55.

Set `DEMO_MODE=0` in the environment to serve the real numbers instead.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# On this branch the demo is the point, so overrides default ON. Any other
# branch should never import this module at all.
enabled: bool = os.environ.get("DEMO_MODE", "1").lower() not in {"0", "false", "no"}

TOTAL = 55
ACTIVE = 35
INACTIVE = 8
STRATEGIC = 3
EXITED = 9
CLOSING = ACTIVE + STRATEGIC  # 38
OPENING = 2
JOINERS = CLOSING - OPENING + EXITED  # 45

SUMMARY_OVERRIDES: dict[str, int | float] = {
    "active_employees": ACTIVE,
    "inactive_employees": INACTIVE,
    "total_employees": TOTAL,
    "closing_headcount": CLOSING,
    "opening_headcount": OPENING,
    "joiners": JOINERS,
    "exits": EXITED,
    # Recomputed from the demo numbers so each percentage matches its own
    # numerator and denominator on screen.
    "active_pct": ACTIVE / TOTAL * 100,
    "attrition_pct": EXITED / TOTAL * 100,
    # Must sum to Exits.
    "voluntary_leavers": 5,
    "involuntary_leavers": 4,
    # Padded from 47/3 so GCC + Non GCC = Total.
    "gcc_employees": 51,
    "non_gcc_employees": 4,
    "senior_lead_employees": 46,
}

# Each dict is the real breakdown shape, padded to total 55.
BREAKDOWN_OVERRIDES: dict[str, object] = {
    "strategic_pool": STRATEGIC,
    # Home "Workforce Category" donut — Active vs Strategic Pool, so it
    # totals Closing Headcount (38), matching the card above it.
    "workforce_category_split": {"Active": ACTIVE, "Strategic Pool": STRATEGIC},
    "status_split": {
        "Active": ACTIVE,
        "Inactive": INACTIVE,
        "Strategic Pool": STRATEGIC,
        "Exited": EXITED,
    },
    "workforce_by_type": {"GCC": 51, "Non GCC": 4},
    "headcount_by_region": {"AMER": 17, "APAC": 1, "EMEA": 35, "Region TBD": 2},
    "workforce_by_working_entity": {
        "AMER": 17,
        "DTAU": 1,
        "DTDE": 5,
        "DTIE": 13,
        "DTNL": 15,
        "DTUK": 2,
        "Entity TBD": 2,
    },
    "headcount_by_seniority": {
        "Premium Lead": 7,
        "Premium Mid": 4,
        "Premium Senior": 9,
        "Premium Technical Service Delivery Manager": 1,
        "Seniority TBD": 7,
        "Standard Lead": 13,
        "Standard Mid": 4,
        "Standard Senior": 10,
    },
    "workforce_by_experience_band": {
        "0-1 Years": 5,
        "3-5 Years": 3,
        "5-8 Years": 13,
        "8+ Years": 34,
    },
    "workforce_by_seniority_category": {
        "Lead": 20,
        "Mid": 8,
        "Other": 1,
        "Senior": 19,
        "TBD": 7,
    },
}

# Monthly series, built so the running total (Opening 2, then +joiners
# -exits each month) lands exactly on Closing Headcount 38 in Jun 2026,
# joiners sum to 45 and exits sum to 9. Keeps the real curve's shape,
# including the April dip.
_MONTHLY = [
    # (month,      joiners, exits, closing)
    ("Jul 2025", 1, 0, 3),
    ("Aug 2025", 2, 0, 5),
    ("Sep 2025", 3, 0, 8),
    ("Oct 2025", 3, 1, 10),
    ("Nov 2025", 4, 0, 14),
    ("Dec 2025", 6, 1, 19),
    ("Jan 2026", 8, 1, 26),
    ("Feb 2026", 6, 0, 32),
    ("Mar 2026", 6, 1, 37),
    ("Apr 2026", 1, 4, 34),
    ("May 2026", 3, 0, 37),
    ("Jun 2026", 2, 1, 38),
]

TREND_OVERRIDES: dict[str, object] = {
    "month_wise_closing_headcount": [
        {"month": month, "closing_headcount": closing} for month, _, _, closing in _MONTHLY
    ],
    "monthly_joiners_vs_leavers": [
        {"month": month, "joiners": joiners, "exits": exits}
        for month, joiners, exits, _ in _MONTHLY
    ],
}


# Attrition drill-down. `exits_table` is deliberately NOT overridden — it
# lists real, named people who left, and padding it to 9 rows would mean
# inventing four employees. It therefore still shows the real 5 rows while
# the charts above it say 9; see the note in the handover.
ATTRITION_OVERRIDES: dict[str, object] = {
    "month_wise_resignation": [
        {"month": month, "exits": exits} for month, _, exits, _ in _MONTHLY
    ],
    "voluntary_involuntary_split": {"Voluntary": 5, "Involuntary": 4},
}


def _apply(model, overrides: dict[str, object]):
    """Return a copy of `model` with the demo values patched in.

    Uses `model_copy(update=...)` so the response model is still the
    validated real object — only the named fields change.
    """
    if not enabled:
        return model
    logger.warning(
        "DEMO_MODE active — serving hardcoded KPI values for %s, not real data",
        type(model).__name__,
    )
    return model.model_copy(update=overrides)


def apply_summary(model):
    return _apply(model, SUMMARY_OVERRIDES)


def apply_breakdowns(model):
    return _apply(model, BREAKDOWN_OVERRIDES)


def apply_trends(model):
    return _apply(model, TREND_OVERRIDES)


def apply_attrition_detail(model):
    return _apply(model, ATTRITION_OVERRIDES)
