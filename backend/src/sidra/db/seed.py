"""Write a snapshot payload into Postgres.

Idempotent by construction: it clears the catalog tables first, so seeding twice yields identical
row counts rather than doubles.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.snapshot import SnapshotPayload
from sidra.db.models import LearnableUnit, Snapshot, TitleAlias, TopicLink, Work
from sidra.db.persist import persist_works
from sidra.db.persist_units import persist_units

EIN_MISHPAT_KIND = "ein_mishpat"
TUR_BRIDGE_KIND = "tur_bridge"
DIRECT_CONFIDENCE = "direct"
INFERRED_CONFIDENCE = "inferred"
_LINK_CHUNK = 5_000


@dataclass(frozen=True, slots=True)
class SeedCounts:
    works: int
    units: int
    aliases: int
    links: int


async def clear_catalog(session: AsyncSession) -> None:
    """Empty the catalog tables, children first."""
    for model in (TopicLink, TitleAlias, LearnableUnit, Work, Snapshot):
        await session.execute(delete(model))
    await session.flush()


async def seed_from_snapshot(session: AsyncSession, payload: SnapshotPayload) -> SeedCounts:
    """Rebuild the catalog from a snapshot. Clears first, so running twice is a no-op."""
    await clear_catalog(session)

    snapshot = Snapshot(
        created_at=payload.created_at,
        sefaria_version=payload.sefaria_version,
        unit_count=sum(draft.unit_count for draft in payload.works),
        edge_count=len(payload.links) + len(payload.bridged),
    )
    session.add(snapshot)
    await session.flush()

    works = await persist_works(session, payload.works, snapshot.id)
    by_ref_title = {work.ref_title: work for work in works}

    grouped: dict[str, list] = {}
    for work_ref_title, row in payload.units:
        grouped.setdefault(work_ref_title, []).append(row)
    unit_total = 0
    for work_ref_title, rows in grouped.items():
        work = by_ref_title.get(work_ref_title)
        if work is None:
            raise ValueError(f"snapshot holds units for {work_ref_title!r}, which is not among its works")
        unit_total += len(await persist_units(session, work, rows, snapshot.id))

    aliases = [
        TitleAlias(
            work_id=by_ref_title[row.ref_title].id,
            alias=row.alias,
            lang=row.lang,
            source=row.source,
        )
        for row in payload.aliases
        if row.ref_title in by_ref_title
    ]
    session.add_all(aliases)

    # Bridged edges are inferences through Tur's siman numbering, never citations. Writing them
    # with the same kind and confidence as a real Ein Mishpat link would make an inference
    # indistinguishable from the apparatus itself.
    for edges, kind, confidence in (
        (payload.links, EIN_MISHPAT_KIND, DIRECT_CONFIDENCE),
        (payload.bridged, TUR_BRIDGE_KIND, INFERRED_CONFIDENCE),
    ):
        for start in range(0, len(edges), _LINK_CHUNK):
            session.add_all(
                [
                    TopicLink(
                        from_ref=edge.citation_1,
                        to_ref=edge.citation_2,
                        from_category=edge.category_1,
                        to_category=edge.category_2,
                        kind=kind,
                        anchor_group=edge.citation_1,
                        confidence=confidence,
                        snapshot_id=snapshot.id,
                    )
                    for edge in edges[start : start + _LINK_CHUNK]
                ]
            )
            await session.flush()
    await session.flush()

    return SeedCounts(
        works=len(works),
        units=unit_total,
        aliases=len(aliases),
        links=len(payload.links) + len(payload.bridged),
    )


async def catalog_is_empty(session: AsyncSession) -> bool:
    """Whether the catalog holds no works. The launcher uses this to decide whether to seed."""
    return (await session.execute(select(Work.id).limit(1))).first() is None
