"""Build ``TrackRow``s for a set of tracks.

Tags and chavrusa names are loaded once for the whole set rather than per track: the Today view
asks for twenty tracks at a time, and twenty round trips for four tag links is the kind of thing
that makes a local app feel slow for no reason.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.models.track_row import TrackRow
from sidra.db.models import Chavrusa, Tag, Track, track_tag
from sidra.ledger.track_state import track_state


async def tags_by_track(session: AsyncSession, track_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    if not track_ids:
        return {}
    rows = (
        await session.execute(
            select(track_tag.c.track_id, Tag.name)
            .join(Tag, Tag.id == track_tag.c.tag_id)
            .where(track_tag.c.track_id.in_(track_ids))
            .order_by(Tag.name)
        )
    ).all()
    grouped: dict[uuid.UUID, list[str]] = {}
    for track_id, name in rows:
        grouped.setdefault(track_id, []).append(name)
    return grouped


async def chavrusa_names(session: AsyncSession) -> dict[uuid.UUID, str]:
    rows = (await session.execute(select(Chavrusa.id, Chavrusa.name))).all()
    return {chavrusa_id: name for chavrusa_id, name in rows}


async def build_rows(session: AsyncSession, tracks: Sequence[Track], on: date) -> list[TrackRow]:
    """One row per track, in the order given."""
    tags = await tags_by_track(session, [track.id for track in tracks])
    names = await chavrusa_names(session)
    rows = []
    for track in tracks:
        state = await track_state(session, track, on)
        rows.append(
            TrackRow.of(
                state,
                tags=tags.get(track.id, []),
                chavrusa=None if track.chavrusa_id is None else names.get(track.chavrusa_id),
            )
        )
    return rows


async def one_row(session: AsyncSession, track_id: uuid.UUID, on: date) -> TrackRow:
    """One track's row, recomputed. The single-track form of ``build_rows``.

    Lives here rather than in a router because both routers answer with it: a read renders it, and
    every write returns it so the screen cannot disagree with the ledger between two round trips.
    """
    track = await track_or_404(session, track_id)
    state = await track_state(session, track, on)
    tags = (await tags_by_track(session, [track.id])).get(track.id, [])
    names = await chavrusa_names(session)
    return TrackRow.of(
        state,
        tags=tags,
        chavrusa=None if track.chavrusa_id is None else names.get(track.chavrusa_id),
    )


async def active_tracks(session: AsyncSession) -> list[Track]:
    """Every active track, ordered so the screen is stable between requests."""
    rows = await session.execute(select(Track).where(Track.is_active.is_(True)).order_by(Track.category, Track.name_en))
    return list(rows.scalars().all())


async def track_or_404(session: AsyncSession, track_id: uuid.UUID) -> Track:
    track = (await session.execute(select(Track).where(Track.id == track_id))).scalar_one_or_none()
    if track is None:
        raise HTTPException(status_code=404, detail=f"no track with id {track_id}")
    return track
