"""Response models for booking (`Sheet1`) endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BookingSummary(BaseModel):
    total_hours: float = Field(..., description="`Total Hours` measure")
    client_hours: float = Field(..., description="`Client Hours` measure")
    internal_hours: float = Field(..., description="`Internal Hours` measure")
    client_hours_pct: float = Field(..., description="`Client Hours %` measure")
    internal_hours_pct: float = Field(..., description="`Internal Hours %` measure")
    hours_split: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Hours grouped by `Booked Hours Type`, from the chart declared in "
            "booking_metrics.yaml. Backs the Internal-v-Client donut. Summed "
            "straight from the data, so a category the config has not seen "
            "still appears rather than being dropped from the donut."
        ),
    )
    total_clients: int = Field(..., description="`Total Clients` measure")
    total_projects: int = Field(..., description="`Total Projects` measure")
    total_regions: int = Field(..., description="`Total Regions` measure")
    markets_covered: int = Field(..., description="`Markets Covered` measure")
