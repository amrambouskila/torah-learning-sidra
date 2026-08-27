from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

MIN_DAYS = 1
MAX_DAYS = 800
"""A yearly cycle needs at least 380; twice that is the most one fetch should ever ask Sefaria for."""


class CalendarRequest(BaseModel):
    """Fetch a span of the Hebrew calendar."""

    model_config = ConfigDict(extra="forbid")

    start: date
    days: int = Field(default=400, ge=MIN_DAYS, le=MAX_DAYS)
