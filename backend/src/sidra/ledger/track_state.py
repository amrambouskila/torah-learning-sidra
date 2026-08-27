"""Everything the app knows about one track today, computed rather than stored.

One function, ``track_state``, and it dispatches on the track's kind because the four kinds owe
their debt differently:

* a chavrusa track has no rate at all -- it carries **staleness**, how long since they last met
* the Chumash owes one aliyah per parsha per day, so a combined week doubles the daily load
* a parsha-weekly work owes one unit per parsha, so a combined week owes two
* everything else owes ``rate`` per period, flat

Nothing here is persisted. It is recomputed per request, so what the screen shows can never drift
from the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.calendar.store import calendar_span
from sidra.db.models import Advance, Track
from sidra.ledger.cycle import cycle_index, fold
from sidra.ledger.cycle_length import cycle_length
from sidra.ledger.effective_anchor import effective_anchor
from sidra.ledger.parsha_schedule import parsha_aliyah_state, parsha_weekly_state
from sidra.ledger.period import Period
from sidra.ledger.position import Position, position_at, track_total
from sidra.ledger.schedule import LedgerState, ledger_state
from sidra.ledger.seed_tracks import actual_ordinal
from sidra.ledger.track_kind import TrackKind


@dataclass(frozen=True, slots=True)
class TrackState:
    """A track as of a given day."""

    track: Track
    total: int
    """Units in one pass. For a cycle track this is one turn, not the running count."""

    actual_ordinal: int
    """Cumulative on a cycle track, so it passes ``total`` and keeps counting."""

    cycle_length: int | None
    """Set when the track repeats -- the Chumash and the parsha-weekly works. None otherwise."""

    at: Position | None
    """Where he stands. None on a track he has not opened."""

    up_next: Position | None
    """The unit due next. None once the track is finished."""

    scheduled_at: Position | None
    """Where the schedule says he should be. None on a chavrusa track, which has no schedule."""

    ledger: LedgerState | None
    """None on a chavrusa track: it carries staleness, not debt."""

    last_advanced_on: date | None
    days_stale: int | None
    """Days since the last advance. None when the track has never moved."""

    @property
    def is_finished(self) -> bool:
        """A cycle track is never finished: at Simchat Torah it begins again."""
        return self.cycle_length is None and self.actual_ordinal >= self.total

    @property
    def cycle_index(self) -> int | None:
        """Which time round he is, counting from 1. None on a track that runs once."""
        if self.cycle_length is None or self.actual_ordinal < 1:
            return None
        return cycle_index(self.actual_ordinal, self.cycle_length)


async def _last_advance(session: AsyncSession, track: Track) -> Advance | None:
    return (
        await session.execute(
            select(Advance)
            .where(Advance.track_id == track.id)
            .order_by(Advance.occurred_at.desc(), Advance.to_ordinal.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _ledger(
    session: AsyncSession, track: Track, actual: int, total: int | None, today: date
) -> LedgerState | None:
    """Compute the debt, by whichever rule this kind of track runs on."""
    if track.period is Period.NONE:
        return None

    if track.kind in (TrackKind.PARSHA_ALIYAH, TrackKind.PARSHA_WEEKLY):
        # The gate must stay ahead of the fetch: a span that has not begun would demand calendar
        # days nobody has stored, and that surfaces as a 409 across the whole screen.
        if track.starts_on is not None and today < track.starts_on:
            return LedgerState.not_started(
                anchor_ordinal=track.anchor_ordinal,
                actual_ordinal=actual,
                starts_on=track.starts_on,
                today=today,
            )
        span = await calendar_span(session, effective_anchor(track.anchor_date, track.starts_on), today)
        state = parsha_aliyah_state if track.kind is TrackKind.PARSHA_ALIYAH else parsha_weekly_state
        return state(
            anchor_ordinal=track.anchor_ordinal,
            actual_ordinal=actual,
            days=span,
            total=total,
        )

    return ledger_state(
        anchor_date=track.anchor_date,
        anchor_ordinal=track.anchor_ordinal,
        rate=track.rate,
        period=track.period,
        actual_ordinal=actual,
        today=today,
        starts_on=track.starts_on,
        total=total,
    )


async def _position_or_none(
    session: AsyncSession, track: Track, ordinal: int, total: int, cycle: int | None
) -> Position | None:
    """A position, or None when the ordinal falls off either end -- unopened, or finished.

    A cycle track only has the near end: past the last unit the address folds round to the first,
    so there is no ordinal beyond which it has nowhere to stand.
    """
    if ordinal < 1:
        return None
    if cycle is not None:
        # The address folds; the ordinal must not. Everything downstream -- the rail's markers,
        # the debt, the picker -- keys on the cumulative number, and a folded one would put the
        # marker a whole cycle back.
        folded = await position_at(session, track, fold(ordinal, cycle))
        return replace(folded, corpus_ordinal=ordinal)
    if ordinal > total:
        return None
    return await position_at(session, track, ordinal)


async def track_state(session: AsyncSession, track: Track, today: date) -> TrackState:
    """Everything the Today view needs about one track."""
    total = await track_total(session, track)
    cycle = await cycle_length(session, track)
    actual = await actual_ordinal(session, track)
    # A cycle track is never clamped: its schedule keeps counting past the end of the turn, which
    # is what makes the debt carry across it instead of freezing.
    ledger = await _ledger(session, track, actual, None if cycle is not None else total, today)
    last = await _last_advance(session, track)
    last_on = last.occurred_at.date() if last is not None else None

    return TrackState(
        track=track,
        total=total,
        cycle_length=cycle,
        actual_ordinal=actual,
        at=await _position_or_none(session, track, actual, total, cycle),
        up_next=await _position_or_none(session, track, actual + 1, total, cycle),
        scheduled_at=(
            None if ledger is None else await _position_or_none(session, track, ledger.scheduled, total, cycle)
        ),
        ledger=ledger,
        last_advanced_on=last_on,
        days_stale=None if last_on is None else (today - last_on).days,
    )
