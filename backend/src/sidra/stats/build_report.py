"""Assemble the Stats report from the ledger, without storing anything."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.calendar.store import calendar_span
from sidra.db.models import Advance, Track
from sidra.ledger.effective_anchor import effective_anchor
from sidra.ledger.period import Period
from sidra.ledger.seed_tracks import SEED_NOTE
from sidra.ledger.track_kind import TrackKind
from sidra.ledger.track_state import TrackState
from sidra.ledger.unit_noun import unit_nouns
from sidra.stats.scheduled_series import fixed_rate_series, parsha_series
from sidra.stats.track_report import TrackReport
from sidra.stats.window import Window

PARSHA_KINDS = (TrackKind.PARSHA_ALIYAH, TrackKind.PARSHA_WEEKLY)


def origin_of(track: Track) -> date:
    """The day this track's schedule began running."""
    return effective_anchor(track.anchor_date, track.starts_on)


def has_begun(track: Track, on: date) -> bool:
    """A track whose start date is still ahead has not begun, and bills nothing."""
    return origin_of(track) <= on


async def learned_by_day(session: AsyncSession, on: date) -> dict[tuple[str, date], int]:
    """Units learned per track per day, ignoring the seeder's opening rows.

    An opening advance places a track at its first unit; counting it as a day's learning would
    credit thirteen sessions that never happened.
    """
    rows = await session.execute(
        select(
            Advance.track_id,
            func.date(Advance.occurred_at).label("day"),
            func.sum(Advance.unit_count),
        )
        .where(func.date(Advance.occurred_at) <= on)
        .where(func.coalesce(Advance.note, "") != SEED_NOTE)
        .group_by(Advance.track_id, func.date(Advance.occurred_at))
    )
    out: dict[tuple[str, date], int] = {}
    for track_id, day, units in rows.all():
        out[(str(track_id), day)] = int(units or 0)
    return out


async def opened_on(session: AsyncSession, on: date) -> dict[str, date]:
    """The first real advance per track."""
    rows = await session.execute(
        select(Advance.track_id, func.min(func.date(Advance.occurred_at)))
        .where(func.date(Advance.occurred_at) <= on)
        .where(func.coalesce(Advance.note, "") != SEED_NOTE)
        .group_by(Advance.track_id)
    )
    return {str(track_id): first for track_id, first in rows.all()}


async def _scheduled(session: AsyncSession, track: Track, window: Window, on: date) -> list[int]:
    origin = origin_of(track)
    # One day before the window too: a day's billing is the difference across it.
    days = [window.start - timedelta(days=1), *window.days]
    if track.kind in PARSHA_KINDS:
        span = await calendar_span(session, origin, on)
        return parsha_series(track, origin, days, span)
    return fixed_rate_series(track, origin, days)


async def report_for(
    session: AsyncSession,
    state: TrackState,
    window: Window,
    learned: dict[tuple[str, date], int],
    first_seen: dict[str, date],
) -> TrackReport:
    """One track's row: what the schedule billed each day against what was learned."""
    track = state.track
    key = str(track.id)
    anchor = state.at or state.up_next or state.scheduled_at
    singular, plural = unit_nouns(anchor.granularity) if anchor is not None else ("unit", "units")

    per_day = [learned.get((key, day), 0) for day in window.days]

    if track.period is Period.NONE:
        # A chavrusa track has no schedule, so nothing is billed and every day it moves is a day
        # the gap closed.
        net = [-units for units in per_day]
        debt_now = None
    else:
        series = await _scheduled(session, track, window, window.end)
        billed = [later - earlier for earlier, later in zip(series[:-1], series[1:], strict=True)]
        net = [bill - units for bill, units in zip(billed, per_day, strict=True)]
        debt_now = None if state.ledger is None else state.ledger.debt

    return TrackReport(
        track_id=key,
        name_en=track.name_en,
        name_he=track.name_he,
        unit_singular=singular,
        unit_plural=plural,
        debt_now=debt_now,
        debt_then=None if debt_now is None else debt_now - sum(net),
        learned_units=sum(per_day),
        days_learned=sum(1 for units in per_day if units > 0),
        last_learned_on=state.last_advanced_on,
        opened_on=first_seen.get(key),
        net=net,
    )


def standing(states: list[TrackState], on: date) -> dict[str, int]:
    """The sidra at a glance, counted in tracks.

    Tracks, never units: twenty-one amudim plus four perakim is not twenty-five of anything.
    """
    counts: dict[str, int] = defaultdict(int)
    for state in states:
        if state.track.period is Period.NONE:
            counts["chavrusa"] += 1
        elif not has_begun(state.track, on):
            counts["not_started"] += 1
        elif state.ledger is None or state.ledger.debt == 0:
            counts["on_pace"] += 1
        elif state.ledger.debt > 0:
            counts["behind"] += 1
        else:
            counts["ahead"] += 1
    for bucket in ("behind", "on_pace", "ahead", "not_started", "chavrusa"):
        counts.setdefault(bucket, 0)
    return dict(counts)
