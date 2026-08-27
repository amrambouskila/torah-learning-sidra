from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from sidra.api.models.track_row import TrackRow


class TodayResponse(BaseModel):
    """The whole sidra for one day, grouped the way the screen is."""

    civil_date: date
    hebrew_date: str
    parsha_en: list[str]
    parsha_he: list[str]
    is_yom_tov: bool
    daily: list[TrackRow]
    shabbat: list[TrackRow]
    chavrusa: list[TrackRow]
