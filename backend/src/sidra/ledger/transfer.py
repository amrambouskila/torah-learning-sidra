"""Move the ledger between machines.

``export_ledger`` reads the database into a document; ``import_ledger`` writes one back. Ids are
carried verbatim, so an import onto the same machine is an exact restore rather than a copy with
new identities -- which matters because an advance is only meaningful attached to its track.

Import clears the ledger first, exactly as ``seed_tracks`` does, so running it twice yields the
same rows rather than doubles. It never touches the catalog: that is ``sidra-db seed``'s job, and
mixing them would let a stale export overwrite a fresher catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.db.models import Advance, CalendarDayRow, Chavrusa, Tag, Track, track_tag
from sidra.ledger.ledger_document import (
    FORMAT_VERSION,
    AdvanceRecord,
    CalendarRecord,
    ChavrusaRecord,
    LedgerDocument,
    TagRecord,
    TrackRecord,
)
from sidra.ledger.seed_tracks import clear_ledger


@dataclass(frozen=True, slots=True)
class TransferCounts:
    chavrusas: int
    tags: int
    tracks: int
    advances: int
    calendar_days: int

    @property
    def total(self) -> int:
        return self.chavrusas + self.tags + self.tracks + self.advances + self.calendar_days


async def _tag_ids_by_track(session: AsyncSession) -> dict[object, list[object]]:
    rows = (await session.execute(select(track_tag.c.track_id, track_tag.c.tag_id))).all()
    grouped: dict[object, list[object]] = {}
    for track_id, tag_id in rows:
        grouped.setdefault(track_id, []).append(tag_id)
    return grouped


async def export_ledger(session: AsyncSession) -> LedgerDocument:
    """Read the whole ledger out of the database, in a stable order."""
    tag_ids = await _tag_ids_by_track(session)

    chavrusas = (await session.execute(select(Chavrusa).order_by(Chavrusa.name))).scalars().all()
    tags = (await session.execute(select(Tag).order_by(Tag.name))).scalars().all()
    tracks = (await session.execute(select(Track).order_by(Track.name_en))).scalars().all()
    advances = (
        (await session.execute(select(Advance).order_by(Advance.occurred_at, Advance.to_ordinal, Advance.id)))
        .scalars()
        .all()
    )
    calendar = (await session.execute(select(CalendarDayRow).order_by(CalendarDayRow.civil_date))).scalars().all()

    return LedgerDocument(
        format_version=FORMAT_VERSION,
        exported_at=datetime.now(UTC),
        chavrusas=[ChavrusaRecord(id=row.id, name=row.name, notes=row.notes) for row in chavrusas],
        tags=[TagRecord(id=row.id, name=row.name, name_he=row.name_he, color=row.color) for row in tags],
        tracks=[
            TrackRecord(
                id=row.id,
                name_en=row.name_en,
                name_he=row.name_he,
                category=row.category,
                kind=row.kind,
                corpus_id=row.corpus_id,
                work_ref_title=row.work_ref_title,
                rate=row.rate,
                period=row.period,
                anchor_date=row.anchor_date,
                anchor_ordinal=row.anchor_ordinal,
                starts_on=row.starts_on,
                chavrusa_id=row.chavrusa_id,
                is_active=row.is_active,
                tag_ids=sorted(tag_ids.get(row.id, []), key=str),  # type: ignore[arg-type]
            )
            for row in tracks
        ],
        advances=[
            AdvanceRecord(
                id=row.id,
                track_id=row.track_id,
                from_ordinal=row.from_ordinal,
                to_ordinal=row.to_ordinal,
                unit_count=row.unit_count,
                occurred_at=row.occurred_at,
                hebrew_date=row.hebrew_date,
                note=row.note,
            )
            for row in advances
        ],
        calendar=[
            CalendarRecord(
                civil_date=row.civil_date,
                hebrew_date=row.hebrew_date,
                parsha_en=list(row.parsha_en),
                parsha_he=list(row.parsha_he),
                is_yom_tov=row.is_yom_tov,
            )
            for row in calendar
        ],
    )


async def import_ledger(session: AsyncSession, document: LedgerDocument) -> TransferCounts:
    """Write a ledger document into the database, replacing whatever is there.

    Validates references first so a hand-edited file fails with a sentence naming the track rather
    than a foreign-key constraint name.
    """
    document.check_references()
    await clear_ledger(session)
    await session.execute(CalendarDayRow.__table__.delete())

    session.add_all([Chavrusa(id=row.id, name=row.name, notes=row.notes) for row in document.chavrusas])
    session.add_all([Tag(id=row.id, name=row.name, name_he=row.name_he, color=row.color) for row in document.tags])
    session.add_all(
        [
            Track(
                id=row.id,
                name_en=row.name_en,
                name_he=row.name_he,
                category=row.category,
                kind=row.kind,
                corpus_id=row.corpus_id,
                work_ref_title=row.work_ref_title,
                rate=row.rate,
                period=row.period,
                anchor_date=row.anchor_date,
                anchor_ordinal=row.anchor_ordinal,
                starts_on=row.starts_on,
                chavrusa_id=row.chavrusa_id,
                is_active=row.is_active,
            )
            for row in document.tracks
        ]
    )
    session.add_all(
        [
            CalendarDayRow(
                civil_date=row.civil_date,
                hebrew_date=row.hebrew_date,
                parsha_en=list(row.parsha_en),
                parsha_he=list(row.parsha_he),
                is_yom_tov=row.is_yom_tov,
            )
            for row in document.calendar
        ]
    )
    await session.flush()

    session.add_all(
        [
            Advance(
                id=row.id,
                track_id=row.track_id,
                from_ordinal=row.from_ordinal,
                to_ordinal=row.to_ordinal,
                unit_count=row.unit_count,
                occurred_at=row.occurred_at,
                hebrew_date=row.hebrew_date,
                note=row.note,
            )
            for row in document.advances
        ]
    )
    associations = [{"track_id": track.id, "tag_id": tag_id} for track in document.tracks for tag_id in track.tag_ids]
    if associations:
        await session.execute(insert(track_tag), associations)
    await session.flush()

    return TransferCounts(
        chavrusas=len(document.chavrusas),
        tags=len(document.tags),
        tracks=len(document.tracks),
        advances=len(document.advances),
        calendar_days=len(document.calendar),
    )
