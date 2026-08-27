from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from sidra.api.models.position_model import PositionModel
from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.reachable import reachable_ceiling
from sidra.ledger.track_kind import TrackKind
from sidra.ledger.track_state import TrackState
from sidra.ledger.unit_noun import unit_nouns


class TrackRow(BaseModel):
    """One track as the Today view shows it: where he is, what he owes, how stale it is."""

    id: uuid.UUID
    name_en: str
    name_he: str
    category: Category
    kind: TrackKind
    period: Period
    rate: int
    total: int
    """Units in one pass. On a cycle track this is one turn, and ``actual_ordinal`` passes it."""

    actual_ordinal: int

    cycle_length: int | None
    """Set when the track repeats annually -- the Chumash and the parsha-weekly works."""

    cycle_index: int | None
    """Which time round he is, counting from 1. None on a track that runs once."""

    reachable_to: int
    """The furthest ordinal the rail may offer and the advance endpoint will accept."""

    unit_singular: str
    unit_plural: str
    """What this track's units are called, so a badge reads "20 amudim behind"."""

    at: PositionModel | None
    up_next: PositionModel | None
    scheduled_at: PositionModel | None

    debt: int | None
    """None on a chavrusa track, which carries staleness rather than debt."""

    days_ahead: int
    is_behind: bool
    starts_in_days: int | None
    starts_on: date | None
    """The declared start date itself. ``starts_in_days`` only survives while it is future, so
    without this "never had one" and "already passed" are indistinguishable."""
    is_finished: bool

    last_advanced_on: date | None
    days_stale: int | None

    tags: list[str]
    chavrusa: str | None

    @classmethod
    def of(cls, state: TrackState, *, tags: list[str], chavrusa: str | None) -> TrackRow:
        ledger = state.ledger
        anchor = state.at or state.up_next or state.scheduled_at
        singular, plural = unit_nouns(anchor.granularity) if anchor is not None else ("unit", "units")
        return cls(
            id=state.track.id,
            cycle_length=state.cycle_length,
            cycle_index=state.cycle_index,
            reachable_to=reachable_ceiling(
                actual=state.actual_ordinal,
                scheduled=None if ledger is None else ledger.scheduled,
                total=state.total,
                cycle_length=state.cycle_length,
            ),
            name_en=state.track.name_en,
            name_he=state.track.name_he,
            category=state.track.category,
            kind=state.track.kind,
            period=state.track.period,
            rate=state.track.rate,
            total=state.total,
            actual_ordinal=state.actual_ordinal,
            unit_singular=singular,
            unit_plural=plural,
            at=PositionModel.of(state.at),
            up_next=PositionModel.of(state.up_next),
            scheduled_at=PositionModel.of(state.scheduled_at),
            debt=None if ledger is None else ledger.debt,
            days_ahead=0 if ledger is None else ledger.days_ahead,
            is_behind=False if ledger is None else ledger.is_behind,
            starts_in_days=None if ledger is None else ledger.starts_in_days,
            starts_on=state.track.starts_on,
            is_finished=state.is_finished,
            last_advanced_on=state.last_advanced_on,
            days_stale=state.days_stale,
            tags=tags,
            chavrusa=chavrusa,
        )
