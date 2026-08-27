from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel


class RoadmapRow(BaseModel):
    """A dated projection for one track.

    ``projected_finish`` already carries the current debt: every day owed slides the date by a day,
    which is the whole reason the roadmap is worth looking at.
    """

    track_id: uuid.UUID
    name_en: str
    name_he: str
    work_ref_title: str | None
    """The work the track is standing in. A track named "Gemara" that holds one masechta projects
    that masechta, and a row saying only "Gemara" overclaims by a factor of thirty-five."""

    corpus_en: str | None
    """The whole body that work belongs to, when it is larger than the track."""

    corpus_total: int | None
    corpus_years: float | None
    """How long the whole body would take at this track's rate. The honest second scale."""

    total: int
    actual_ordinal: int
    units_remaining: int
    rate_per_day: float
    debt: int
    projected_finish: date | None
    """None on a chavrusa track, which has no rate to project from."""

    yearly_cycle_rate: float
    """How many units a day a full cycle in a year would take. The Pace Explorer's number."""
