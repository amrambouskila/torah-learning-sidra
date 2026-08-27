"""Stats: whether the gap is opening or closing, per track and across the sidra.

A habit tracker asks "did you show up?". A debt ledger asks "is the gap opening or closing?", and
that is what this answers. Every value is reconstructed from the advances and the schedule; the
endpoint stores nothing and mutates nothing.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.deps import get_session, today
from sidra.api.models.stats_response import StatsResponse, StatsStanding, StatsStreak
from sidra.api.models.stats_track import StatsTrack
from sidra.api.track_rows import active_tracks
from sidra.db.models import Advance
from sidra.ledger.seed_tracks import SEED_NOTE
from sidra.ledger.track_state import track_state
from sidra.stats.build_report import has_begun, learned_by_day, opened_on, origin_of, report_for, standing
from sidra.stats.streak import current_run, longest_run
from sidra.stats.window import MAX_WINDOW_DAYS, MIN_WINDOW_DAYS, window_for

router = APIRouter(prefix="/api", tags=["stats"])

DEFAULT_WINDOW_DAYS = 30


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    on: date | None = None,
    window: int = Query(default=DEFAULT_WINDOW_DAYS, ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS),
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> StatsResponse:
    """The window is clamped to the ledger's own age, and says so in the response."""
    day = on or default_day
    tracks = await active_tracks(session)

    begun = [track for track in tracks if has_begun(track, day)]
    earliest = min((origin_of(track) for track in begun), default=None)
    span = window_for(on=day, requested_days=window, earliest_origin=earliest)

    try:
        states = [await track_state(session, track, day) for track in tracks]
        learned = await learned_by_day(session, day)
        first_seen = await opened_on(session, day)
        reports = [
            await report_for(session, state, span, learned, first_seen)
            for state in states
            if has_begun(state.track, day)
        ]
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    active_days = (
        (
            await session.execute(
                select(func.distinct(func.date(Advance.occurred_at)))
                .where(func.date(Advance.occurred_at) <= day)
                .where(func.coalesce(Advance.note, "") != SEED_NOTE)
            )
        )
        .scalars()
        .all()
    )

    return StatsResponse(
        on=day,
        days=span.days,
        window_days=span.length,
        requested_window_days=span.requested_days,
        standing=StatsStanding(**standing(states, day)),
        streak=StatsStreak(current=current_run(active_days, on=day), longest=longest_run(active_days)),
        tracks=[
            StatsTrack(
                track_id=report.track_id,
                name_en=report.name_en,
                name_he=report.name_he,
                unit_singular=report.unit_singular,
                unit_plural=report.unit_plural,
                debt_now=report.debt_now,
                debt_then=report.debt_then,
                learned_units=report.learned_units,
                days_learned=report.days_learned,
                last_learned_on=report.last_learned_on,
                opened_on=report.opened_on,
                net=report.net,
            )
            for report in reports
        ],
    )
