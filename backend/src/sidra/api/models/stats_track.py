from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class StatsTrack(BaseModel):
    """One track's row in the Stats grid: what it was billed against what was learned."""

    track_id: str
    name_en: str
    name_he: str
    unit_singular: str
    unit_plural: str

    debt_now: int | None
    """None on a chavrusa track, which carries staleness rather than debt."""

    debt_then: int | None
    """The debt on the window's first day, so the direction of travel is visible at a glance."""

    learned_units: int
    days_learned: int
    last_learned_on: date | None
    opened_on: date | None
    """First real advance. None means never opened, which is not the same as opened and idle."""

    net: list[int]
    """Billed minus learned, one value per day. Positive opened the gap, negative closed it."""
