"""Everything that changes a track: its tags, its start date, and where it stands.

Split from ``tracks.py`` so the read routes and the write routes can be read separately. Both mount
under ``/api/tracks``, so no path moves and no client can tell.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.deps import get_session, safety_copy_path, today
from sidra.api.models.advance_request import AdvanceRequest
from sidra.api.models.advance_result import AdvanceResult
from sidra.api.models.correction_result import CorrectionResult
from sidra.api.models.position_write import PositionUpdate
from sidra.api.models.schedule_write import ScheduleUpdate
from sidra.api.models.track_row import TrackRow
from sidra.api.models.track_tags_write import TrackTagsUpdate
from sidra.api.models.track_write import TrackStartUpdate
from sidra.api.track_rows import one_row, track_or_404
from sidra.calendar.store import calendar_day
from sidra.db.models import Advance, Tag, Track, track_tag
from sidra.ledger.cycle import align_to, fold
from sidra.ledger.cycle_length import cycle_length
from sidra.ledger.locate import resolve_position
from sidra.ledger.period import Period
from sidra.ledger.position import position_at
from sidra.ledger.reachable import reachable_ceiling
from sidra.ledger.reanchor import reanchor
from sidra.ledger.rebase import rebase_start
from sidra.ledger.recalibrate import recalibrated_anchor
from sidra.ledger.safety_copy import write_safety_copy
from sidra.ledger.seed_tracks import actual_ordinal
from sidra.ledger.track_state import track_state
from sidra.ledger.truncate import truncate_to
from sidra.ledger.unit_noun import unit_nouns

router = APIRouter(prefix="/api/tracks", tags=["tracks"])

ADVANCE_HOUR = time(12, 0)
MAX_START_YEARS_AHEAD = 2


@router.put("/{track_id}/tags", response_model=TrackRow)
async def set_track_tags(
    track_id: uuid.UUID,
    body: TrackTagsUpdate,
    on: date | None = None,
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> TrackRow:
    """Replace the whole set of tags this track wears.

    Returns the recomputed row, because the pills the caller draws come off it and a second round
    trip would let the screen disagree with the ledger in between.
    """
    day = on or default_day
    track = await track_or_404(session, track_id)

    wanted = set(body.tag_ids)
    if wanted:
        known = set((await session.execute(select(Tag.id).where(Tag.id.in_(wanted)))).scalars().all())
        missing = sorted(str(tag_id) for tag_id in wanted - known)
        if missing:
            raise HTTPException(status_code=404, detail=f"no tag with id {missing[0]}")

    await session.execute(delete(track_tag).where(track_tag.c.track_id == track.id))
    for tag_id in wanted:
        await session.execute(insert(track_tag).values(track_id=track.id, tag_id=tag_id))
    await session.flush()

    try:
        return await one_row(session, track_id, day)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.patch("/{track_id}", response_model=TrackRow)
async def set_start_date(
    track_id: uuid.UUID,
    body: TrackStartUpdate,
    on: date | None = None,
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> TrackRow:
    """Set, move or clear the day a track's schedule begins.

    Setting a date rebases the anchor onto it, which clears whatever the track accrued while it
    sat unopened -- the point of the feature for a sefer not started yet.

    On a track carrying a real backlog that same clearing would be destructive, so it is refused
    unless the caller says ``forgive``. The discriminator is the debt itself, not whether an
    opening position was ever recorded: a track seeded at its first unit from the old note has a
    position but owes nothing, and refusing it there was refusing a change that erased nothing.
    """
    day = on or default_day
    track = await track_or_404(session, track_id)

    if track.period is Period.NONE:
        raise HTTPException(
            status_code=422,
            detail=f"{track.name_en} is a chavrusa track; it carries staleness, not a schedule to start",
        )

    starts_on = body.starts_on
    if starts_on is not None:
        if starts_on < day:
            raise HTTPException(
                status_code=422,
                detail=f"{starts_on} is in the past; a track cannot start before today",
            )
        if starts_on > day.replace(year=day.year + MAX_START_YEARS_AHEAD):
            raise HTTPException(
                status_code=422,
                detail=f"{starts_on} is more than {MAX_START_YEARS_AHEAD} years out",
            )

    actual = await actual_ordinal(session, track)
    running = track.starts_on is None or day >= track.starts_on
    # Both halves matter. A track never opened owes only what it accrued while it sat unread,
    # and clearing that is the whole feature. A track opened and owing has a real backlog.
    if starts_on is not None and running and actual > 0 and not body.forgive:
        try:
            state = await track_state(session, track, day)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        owed = 0 if state.ledger is None else state.ledger.debt
        if owed > 0:
            anchor = state.at or state.up_next or state.scheduled_at
            singular, plural = unit_nouns(anchor.granularity) if anchor is not None else ("unit", "units")
            noun = singular if owed == 1 else plural
            raise HTTPException(
                status_code=422,
                detail=f"{track.name_en} owes {owed} {noun}; setting a start date clears that",
            )

    rebase_start(track, starts_on, actual_ordinal=actual, today=day)
    await session.flush()

    try:
        return await one_row(session, track_id, day)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{track_id}/advance", response_model=AdvanceResult)
async def advance(
    track_id: uuid.UUID,
    body: AdvanceRequest,
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> AdvanceResult:
    """Record a movement along a track.

    The destination is absolute -- where he got to, not how far he went -- so posting the same
    advance twice is a no-op rather than a double count. The most likely double post is a retried
    request, not a second session of learning.
    """
    track = await track_or_404(session, track_id)
    try:
        occurred_on = date.fromisoformat(body.occurred_on) if body.occurred_on else default_day
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"{body.occurred_on!r} is not a date") from error

    current = await actual_ordinal(session, track)
    cycle_len = await cycle_length(session, track)
    try:
        if body.to_ref is not None:
            # Resolve against where he is *standing*, which on a cycle track is the folded
            # address; the cumulative ordinal names no unit in the catalog.
            here = current if cycle_len is None or current < 1 else fold(current, cycle_len)
            base = await resolve_position(session, track, body.to_ref, current_ordinal=here)
            destination = base if cycle_len is None else align_to(base, current, cycle_len)
        else:
            assert body.to_ordinal is not None  # noqa: S101 - the model guarantees one or the other
            destination = body.to_ordinal
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        state_before = await track_state(session, track, occurred_on)
        ceiling = reachable_ceiling(
            actual=state_before.actual_ordinal,
            scheduled=None if state_before.ledger is None else state_before.ledger.scheduled,
            total=state_before.total,
            cycle_length=state_before.cycle_length,
        )
        if destination > ceiling:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{track.name_en}: {destination} is past the end; the track holds {state_before.total} units"
                    if state_before.cycle_length is None
                    else f"{track.name_en}: {destination} is more than one whole cycle ahead"
                ),
            )
        hebrew_date = (await calendar_day(session, occurred_on)).hebrew_date
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    if destination <= current:
        return AdvanceResult(
            advance_id=None,
            resolved_ordinal=destination,
            from_ordinal=current,
            to_ordinal=current,
            unit_count=0,
            was_replay=True,
            track=await one_row(session, track_id, occurred_on),
        )

    row = Advance(
        track_id=track.id,
        from_ordinal=current,
        to_ordinal=destination,
        unit_count=destination - current,
        occurred_at=datetime.combine(occurred_on, ADVANCE_HOUR, tzinfo=UTC),
        hebrew_date=hebrew_date,
        note=body.note,
    )
    session.add(row)
    await session.flush()

    return AdvanceResult(
        advance_id=row.id,
        resolved_ordinal=destination,
        from_ordinal=row.from_ordinal,
        to_ordinal=row.to_ordinal,
        unit_count=row.unit_count,
        was_replay=False,
        track=await one_row(session, track_id, occurred_on),
    )


async def _correction_warning(session: AsyncSession, track: Track, current: int, destination: int) -> str:
    """Name both positions and the cost, so the confirmation is never a blank "are you sure"."""
    cycle_len = await cycle_length(session, track)
    here = await position_at(session, track, current if cycle_len is None else fold(current, cycle_len))
    there = await position_at(session, track, destination if cycle_len is None else fold(destination, cycle_len))
    dropped = current - destination
    singular, plural = unit_nouns(here.granularity)
    noun = singular if dropped == 1 else plural
    return (
        f"{track.name_en}: {there.ref} is {dropped} {noun} behind {here.ref}; "
        f"this removes {dropped} {noun} of recorded learning. There is no undo."
    )


@router.put("/{track_id}/position", response_model=CorrectionResult)
async def correct_position(
    track_id: uuid.UUID,
    body: PositionUpdate,
    on: date | None = None,
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
    safety_copy: Path = Depends(safety_copy_path),
) -> CorrectionResult:
    """Move a track's actual position backwards, rewriting the rows behind it.

    Only backwards. A destination ahead is an advance, and sending it here would make an endpoint
    named for correction record learning instead.
    """
    day = on or default_day
    track = await track_or_404(session, track_id)
    current = await actual_ordinal(session, track)
    cycle_len = await cycle_length(session, track)

    try:
        if body.to_ref is not None:
            here = current if cycle_len is None or current < 1 else fold(current, cycle_len)
            base = await resolve_position(session, track, body.to_ref, current_ordinal=here)
            destination = base if cycle_len is None else align_to(base, current, cycle_len)
        else:
            assert body.to_ordinal is not None  # noqa: S101 - the model guarantees one or the other
            destination = body.to_ordinal
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if destination > current:
        raise HTTPException(
            status_code=422,
            detail=f"{track.name_en}: {destination} is ahead of where you are; record it as an advance",
        )

    try:
        if destination == current:
            return CorrectionResult(
                from_ordinal=current,
                to_ordinal=current,
                removed_units=0,
                removed_advances=0,
                moved=False,
                track=await one_row(session, track_id, day),
            )

        if not body.confirm:
            raise HTTPException(status_code=422, detail=await _correction_warning(session, track, current, destination))

        # The only gesture in the app that destroys recorded learning, and there is no undo of an
        # undo -- so the whole ledger goes to disk first, and a copy that cannot be written stops
        # the deletion rather than being skipped past.
        try:
            await write_safety_copy(session, safety_copy)
        except OSError as error:
            raise HTTPException(
                status_code=409,
                detail=f"could not write the safety copy at {safety_copy}; nothing was changed ({error})",
            ) from error

        result = await truncate_to(session, track, destination)
        return CorrectionResult(
            from_ordinal=result.from_ordinal,
            to_ordinal=result.to_ordinal,
            removed_units=result.removed_units,
            removed_advances=result.removed_advances,
            moved=True,
            track=await one_row(session, track_id, day),
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _check_start_day(track: Track, started_on: date, today_is: date) -> None:
    """A schedule cannot begin in the future, and one that has not begun is not this route's."""
    if started_on > today_is:
        raise HTTPException(
            status_code=422,
            detail=f"{started_on} is after today; a schedule cannot begin in the future",
        )
    if track.starts_on is not None and track.starts_on > today_is:
        raise HTTPException(
            status_code=422,
            detail=f"{track.name_en} has not begun; move its start date with PATCH instead",
        )


async def _shift_opening_position(session: AsyncSession, track: Track, body: ScheduleUpdate, today_is: date) -> None:
    """Solve the anchor backwards from the ordinal the schedule should read today."""
    try:
        state = await track_state(session, track, today_is)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    try:
        if body.to_ref is not None:
            desired = await resolve_position(session, track, body.to_ref, current_ordinal=state.actual_ordinal)
        else:
            assert body.to_ordinal is not None  # noqa: S101 - the model guarantees exactly one
            desired = body.to_ordinal
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    assert state.ledger is not None  # noqa: S101 - Period.NONE was refused before this was called
    ceiling = reachable_ceiling(
        actual=state.actual_ordinal,
        scheduled=state.ledger.scheduled,
        total=state.total,
        cycle_length=state.cycle_length,
    )
    if desired > ceiling:
        raise HTTPException(status_code=422, detail=f"{track.name_en}: {desired} is past the end of the track")

    anchor = recalibrated_anchor(track, desired, state.ledger.scheduled)
    if anchor < 1:
        raise HTTPException(
            status_code=422,
            detail=f"{track.name_en}: that would put the schedule's origin before its first unit",
        )
    track.anchor_ordinal = anchor


@router.put("/{track_id}/schedule", response_model=TrackRow)
async def correct_schedule(
    track_id: uuid.UUID,
    body: ScheduleUpdate,
    on: date | None = None,
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> TrackRow:
    """Correct what a track is supposed to be up to, by whichever operand was wrong.

    Nothing is destroyed and both routes state an absolute fact rather than applying a delta, so
    there is no acknowledgement to give and sending the previous value back restores it exactly.
    """
    day = on or default_day
    track = await track_or_404(session, track_id)
    if track.period is Period.NONE:
        raise HTTPException(
            status_code=422,
            detail=f"{track.name_en} is a chavrusa track; it carries staleness, not a schedule to correct",
        )

    if body.started_on is not None:
        _check_start_day(track, body.started_on, day)
        reanchor(track, body.started_on)
    else:
        await _shift_opening_position(session, track, body, day)

    await session.flush()
    try:
        return await one_row(session, track_id, day)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
