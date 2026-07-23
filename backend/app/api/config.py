"""Read-only routes serving frontend config — filter definitions today,
potentially more later. Keeps the frontend from re-declaring what the
backend YAML already says (labels, hierarchy, page mapping); option
VALUES stay data-derived from the existing `/roster/filter-options` and
`/utilization/filter-options` endpoints.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.security import get_current_user
from app.db.models import User
from app.services import metric_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])


class FilterDefinition(BaseModel):
    key: str
    label: str
    type: Literal["single", "multi", "hierarchical"]
    column_role: str | None = None
    derived_from_chart: str | None = None
    nests: str | None = None
    applies_to_pages: list[str] = []


class FilterConfigResponse(BaseModel):
    dataset: Literal["roster", "booking"]
    filters: list[FilterDefinition]


@router.get("/filters", response_model=FilterConfigResponse)
def get_filter_config(
    dataset: str = Query("roster"),
    user: User = Depends(get_current_user),
) -> FilterConfigResponse:
    """Filter DEFINITIONS (labels, hierarchy, page mapping) for one dataset.

    Option VALUES are not returned here — the frontend fetches them from
    `/roster/filter-options` and `/utilization/filter-options`, both of
    which stay data-derived so a new region/department appears without a
    config edit.
    """
    if dataset not in ("roster", "booking"):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown dataset {dataset!r}; expected 'roster' or 'booking'.",
        )
    try:
        raw = metric_config.filters(dataset)
    except Exception:
        logger.exception("get_filter_config: failed to load filter config for %s", dataset)
        raise HTTPException(status_code=500, detail="Failed to load filter config")
    items = [
        FilterDefinition(
            key=key,
            label=spec.get("label", key),
            type=spec.get("type", "multi"),
            column_role=spec.get("column_role"),
            derived_from_chart=spec.get("derived_from_chart"),
            nests=spec.get("nests"),
            applies_to_pages=list(spec.get("applies_to_pages", []) or []),
        )
        for key, spec in raw.items()
    ]
    return FilterConfigResponse(dataset=dataset, filters=items)  # type: ignore[arg-type]
