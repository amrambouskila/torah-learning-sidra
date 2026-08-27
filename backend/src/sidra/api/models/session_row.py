from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class SessionRow(BaseModel):
    """One recorded chavrusa session."""

    occurred_on: date
    hebrew_date: str
    from_ordinal: int
    to_ordinal: int
    unit_count: int
    note: str | None
