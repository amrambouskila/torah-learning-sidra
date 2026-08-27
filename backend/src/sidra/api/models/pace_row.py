from __future__ import annotations

from pydantic import BaseModel


class PaceRow(BaseModel):
    """One body of learning and what a full cycle through it would cost.

    Aspirational and deliberately not a track: several rows have no track at all, two bodies appear
    twice at different granularities, and nothing here reads the ledger. The horizon is a
    **duration**, never a date, so it can never be mistaken for the Roadmap's finish line.
    """

    row_id: str
    scope_en: str
    unit_singular: str
    unit_plural: str
    total: int

    per_day_for_horizon: float
    """Units a day to finish inside the chosen horizon."""

    years_at_rate: float
    """How long the chosen rate would take. A duration in years, not a date."""

    note: str | None = None
