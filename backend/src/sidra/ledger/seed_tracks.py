"""Seed Amram's real sidra into Postgres.

Idempotent by construction: it clears the ledger tables first, so seeding twice yields the same
rows rather than doubles. It never touches the catalog -- ``sidra-db seed`` owns that, and this
runs against whatever catalog is already there.

The two positions in ``tracks.yaml`` become two different things:

  ``scheduled_ref``  -> ``anchor_ordinal`` at ``anchor_date = as_of``, so on that day the schedule
                        reads exactly the scheduled reference and every later day accrues from it
  ``current_ref``    -> one opening ``Advance``, which is where the actual position comes from

A track with no ``scheduled_ref`` anchors on its current position, so it starts square. A track
with no current position has not been opened and its actual ordinal is zero.

A track that declares ``starts_on`` anchors on *that* day instead of on ``as_of``, at one unit
past where it stands -- the start day is a learning day, so the first unit is due on it. Without
that, a track waiting seven weeks to begin would open seven units behind.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.calendar.store import calendar_day
from sidra.db.models import Advance, Chavrusa, Tag, Track, track_tag
from sidra.ledger.locate import ordinal_for_aliyah, ordinal_for_ref
from sidra.ledger.track_spec import TrackSpec
from sidra.ledger.tracks_file import TracksFile, load_tracks_file

SEED_NOTE = "Opening position, from the Obsidian sidra."
SEED_HOUR = time(12, 0)


@dataclass(frozen=True, slots=True)
class TrackSeedCounts:
    tracks: int
    chavrusas: int
    tags: int
    advances: int
    tagged: int


async def clear_ledger(session: AsyncSession) -> None:
    """Empty the ledger tables, children first. The catalog is left alone."""
    await session.execute(delete(track_tag))
    for model in (Advance, Track, Tag, Chavrusa):
        await session.execute(delete(model))
    await session.flush()


async def _current_ordinal(session: AsyncSession, track: Track, spec: TrackSpec) -> int | None:
    """Where the track actually stands, or None if it has not been opened."""
    if spec.current_ref is not None:
        return await ordinal_for_ref(session, track, spec.current_ref)
    if spec.current_aliyah is not None:
        return await ordinal_for_aliyah(session, track, spec.current_aliyah.parsha, spec.current_aliyah.aliyah)
    return None


async def seed_tracks(session: AsyncSession, tracks_file: TracksFile | None = None) -> TrackSeedCounts:
    """Rebuild the ledger from ``tracks.yaml``. Clears first, so running twice is a no-op.

    Requires the calendar to be seeded for ``as_of``: every advance carries the Hebrew date it
    happened on, and inventing one would put a wrong date on the app's first twenty rows.
    """
    spec_file = tracks_file if tracks_file is not None else load_tracks_file()
    await clear_ledger(session)

    hebrew_date = (await calendar_day(session, spec_file.as_of)).hebrew_date
    occurred_at = datetime.combine(spec_file.as_of, SEED_HOUR, tzinfo=UTC)

    tags = {spec.name: Tag(name=spec.name, name_he=spec.name_he, color=spec.color) for spec in spec_file.tags}
    chavrusas = {name: Chavrusa(name=name) for name in spec_file.chavrusas}
    session.add_all([*tags.values(), *chavrusas.values()])
    await session.flush()

    advances = 0
    tagged: list[dict[str, uuid.UUID]] = []

    for spec in spec_file.tracks:
        track = Track(
            name_en=spec.name_en,
            name_he=spec.name_he,
            category=spec.category,
            kind=spec.kind,
            corpus_id=spec.corpus_id,
            work_ref_title=spec.work_ref_title,
            rate=spec.rate,
            period=spec.period,
            anchor_date=spec.starts_on or spec_file.as_of,
            anchor_ordinal=1,
            starts_on=spec.starts_on,
            chavrusa_id=None if spec.chavrusa is None else chavrusas[spec.chavrusa].id,
            is_active=True,
        )
        session.add(track)
        await session.flush()

        current = await _current_ordinal(session, track, spec)
        if spec.starts_on is not None:
            track.anchor_ordinal = (current or 0) + spec.rate
        elif spec.scheduled_ref is not None:
            track.anchor_ordinal = await ordinal_for_ref(session, track, spec.scheduled_ref)
        elif current is not None:
            track.anchor_ordinal = current

        if current is not None:
            session.add(
                Advance(
                    track_id=track.id,
                    from_ordinal=max(0, current - spec.rate),
                    to_ordinal=current,
                    unit_count=min(spec.rate, current),
                    occurred_at=occurred_at,
                    hebrew_date=hebrew_date,
                    note=SEED_NOTE,
                )
            )
            advances += 1

        tagged.extend({"track_id": track.id, "tag_id": tags[name].id} for name in spec.tags)

    if tagged:
        await session.execute(insert(track_tag), tagged)
    await session.flush()

    return TrackSeedCounts(
        tracks=len(spec_file.tracks),
        chavrusas=len(chavrusas),
        tags=len(tags),
        advances=advances,
        tagged=len(tagged),
    )


async def actual_ordinal(session: AsyncSession, track: Track) -> int:
    """Where the track actually stands: the furthest advance recorded, or zero if none is.

    Zero means the first unit is owed and nothing has been learned -- the state of the four sefarim
    Amram has not opened yet.
    """
    furthest = await session.scalar(
        select(Advance.to_ordinal).where(Advance.track_id == track.id).order_by(Advance.to_ordinal.desc()).limit(1)
    )
    return int(furthest or 0)


async def ledger_is_empty(session: AsyncSession) -> bool:
    """Whether the ledger holds no tracks. The launcher uses this to decide whether to seed."""
    return (await session.execute(select(Track.id).limit(1))).first() is None
