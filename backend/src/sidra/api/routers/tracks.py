"""The track list and one track's rail. Everything that mutates a track lives in ``track_writes``."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.deps import get_session, today
from sidra.api.models.rail_unit import RailUnit
from sidra.api.models.track_detail import TrackDetail
from sidra.api.models.track_row import TrackRow
from sidra.api.sefaria_url import sefaria_url
from sidra.api.track_rows import active_tracks, build_rows, one_row, track_or_404
from sidra.db.models import Track
from sidra.ledger.cycle import fold
from sidra.ledger.position import position_at
from sidra.ledger.reachable import reachable_ceiling
from sidra.ledger.track_state import track_state

router = APIRouter(prefix="/api/tracks", tags=["tracks"])

DEFAULT_RAIL_RADIUS = 12
MAX_RAIL_RADIUS = 100
MAX_RAIL_SPAN = 500
"""The Mishneh Torah chavrusa tracks are 15,143 halachos. The Track screen scrolls the spine and
fetches spans as they come into view, so no single call ever has to carry the whole thing."""


@router.get("", response_model=list[TrackRow])
async def list_tracks(
    on: date | None = None,
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> list[TrackRow]:
    try:
        return await build_rows(session, await active_tracks(session), on or default_day)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{track_id}", response_model=TrackDetail)
async def get_track(
    track_id: uuid.UUID,
    on: date | None = None,
    radius: int = Query(default=DEFAULT_RAIL_RADIUS, ge=0, le=MAX_RAIL_RADIUS),
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> TrackDetail:
    """One track with a window of its rail around both markers."""
    day = on or default_day
    track = await track_or_404(session, track_id)
    try:
        state = await track_state(session, track, day)
        row = await one_row(session, track_id, day)

        scheduled = state.ledger.scheduled if state.ledger is not None else None
        markers = [ordinal for ordinal in (state.actual_ordinal, scheduled) if ordinal] or [1]
        ceiling = reachable_ceiling(
            actual=state.actual_ordinal,
            scheduled=scheduled,
            total=state.total,
            cycle_length=state.cycle_length,
        )
        low = max(1, min(markers) - radius)
        high = min(ceiling, max(markers) + radius)
        # The span is the debt when radius is 0, and a debt has no upper bound once a cycle track
        # stops clamping. Without this the Track screen walks position_at once per unit owed.
        high = min(high, low + MAX_RAIL_SPAN - 1)

        rail = await _rail_span(session, track, low, high, state.actual_ordinal, scheduled, state.cycle_length)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return TrackDetail(track=row, rail=rail, rail_from=low, rail_to=high)


async def _rail_span(
    session: AsyncSession,
    track: Track,
    low: int,
    high: int,
    actual: int,
    scheduled: int | None,
    cycle: int | None = None,
) -> list[RailUnit]:
    rail = []
    for ordinal in range(low, high + 1):
        position = await position_at(session, track, ordinal if cycle is None else fold(ordinal, cycle))
        rail.append(
            RailUnit(
                ordinal=ordinal,
                ref=position.ref,
                work_title_en=position.work_ref_title,
                work_title_he=position.work_title_he,
                label_en=position.label_en,
                label_he=position.label_he,
                sefaria_url=sefaria_url(position.ref) if position.is_linkable else None,
                is_actual=ordinal == actual,
                is_scheduled=ordinal == scheduled,
            )
        )
    return rail


@router.get("/{track_id}/rail", response_model=list[RailUnit])
async def get_rail(
    track_id: uuid.UUID,
    start: int = Query(ge=1, alias="from"),
    end: int = Query(ge=1, alias="to"),
    on: date | None = None,
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> list[RailUnit]:
    """One span of a track's rail, so the Track screen can scroll a 15,143-unit spine.

    The span is clamped to the track rather than refused at the far end: a viewport that runs past
    the last unit is ordinary scrolling, not a mistake.
    """
    if end < start:
        raise HTTPException(status_code=422, detail=f"to ({end}) precedes from ({start})")
    if end - start + 1 > MAX_RAIL_SPAN:
        raise HTTPException(
            status_code=422, detail=f"a rail span holds at most {MAX_RAIL_SPAN} units, asked for {end - start + 1}"
        )

    track = await track_or_404(session, track_id)
    try:
        state = await track_state(session, track, on or default_day)
        scheduled = state.ledger.scheduled if state.ledger is not None else None
        ceiling = reachable_ceiling(
            actual=state.actual_ordinal,
            scheduled=scheduled,
            total=state.total,
            cycle_length=state.cycle_length,
        )
        if start > ceiling:
            return []
        return await _rail_span(
            session, track, start, min(end, ceiling), state.actual_ordinal, scheduled, state.cycle_length
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
