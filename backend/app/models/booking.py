"""Response models for booking (`Sheet1`) endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BookingSummary(BaseModel):
    total_hours: float = Field(..., description="`Total Hours` measure")
    client_hours: float = Field(..., description="`Client Hours` measure")
    internal_hours: float = Field(..., description="`Internal Hours` measure")
    client_hours_pct: float = Field(..., description="`Client Hours %` measure")
    internal_hours_pct: float = Field(..., description="`Internal Hours %` measure")
    total_clients: int = Field(..., description="`Total Clients` measure")
    total_projects: int = Field(..., description="`Total Projects` measure")
    total_regions: int = Field(..., description="`Total Regions` measure")
    markets_covered: int = Field(..., description="`Markets Covered` measure")
