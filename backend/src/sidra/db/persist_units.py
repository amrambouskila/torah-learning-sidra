from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.ref import to_ref
from sidra.catalog.stored_unit import StoredUnitRow
from sidra.db.models import LearnableUnit, Work


async def persist_units(
    session: AsyncSession,
    work: Work,
    rows: Sequence[StoredUnitRow],
    snapshot_id: uuid.UUID,
) -> list[LearnableUnit]:
    """Write stored units for one work, resolving parent_seq to parent_id.

    The parents are flushed first so they have ids; an orphan parent_seq raises rather than
    silently writing a null parent.
    """
    if not rows:
        raise ValueError(f"no rows supplied for {work.ref_title!r}")

    by_seq: dict[int, LearnableUnit] = {}
    for row in rows:
        unit = LearnableUnit(
            work_id=work.id,
            seq=row.seq,
            ref_title=work.ref_title,
            addr=list(row.addr),
            addr_types=list(row.addr_types),
            index_title=work.index_title,
            source=work.source,
            snapshot_id=snapshot_id,
            is_range=row.is_range,
            resolved_ref=row.resolved_ref,
            resolved_he_ref=row.resolved_he_ref,
            granularity=row.granularity,
            label_en=row.label_en,
            label_he=row.label_he,
            ordinal=row.ordinal,
            child_count=row.child_count,
        )
        session.add(unit)
        by_seq[row.seq] = unit
    await session.flush()

    for row in rows:
        if row.parent_seq is None:
            continue
        parent = by_seq.get(row.parent_seq)
        if parent is None:
            raise ValueError(f"unit seq {row.seq} names parent seq {row.parent_seq}, which is not in this batch")
        by_seq[row.seq].parent_id = parent.id
    await session.flush()

    return [by_seq[row.seq] for row in rows]


def stored_unit_ref(work: Work, row: StoredUnitRow) -> str:
    """The pointer ref for a stored unit -- not its expansion, which lives in resolved_ref."""
    return to_ref(work.ref_title, row.addr)
