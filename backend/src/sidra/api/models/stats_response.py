from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from sidra.api.models.stats_track import StatsTrack


class StatsStanding(BaseModel):
    """The sidra at a glance, counted in tracks rather than units."""

    behind: int
    on_pace: int
    ahead: int
    not_started: int
    chavrusa: int


class StatsStreak(BaseModel):
    """Consecutive days with something recorded, across the whole sidra."""

    current: int
    longest: int


class StatsResponse(BaseModel):
    """Everything the Stats screen draws."""

    on: date
    days: list[date]
    """The window's columns, in order. Never empty."""

    window_days: int
    requested_window_days: int
    """What was asked for. The window is clamped to the ledger's own age, and a report that hides
    the clamp claims a history it does not have."""

    standing: StatsStanding
    streak: StatsStreak
    tracks: list[StatsTrack]
