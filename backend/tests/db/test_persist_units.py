from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.catalog.stored_unit import StoredUnitRow
from sidra.catalog.work_draft import WorkDraft
from sidra.db.models import LearnableUnit, Snapshot
from sidra.db.persist import persist_works
from sidra.db.persist_units import persist_units, stored_unit_ref

pytestmark = pytest.mark.integration

PARSHA_DRAFT = WorkDraft(
    corpus_id="torah",
    corpus_seq=100,
    index_title=None,
    ref_title="Parashat HaShavua",
    title_he="פרשת השבוע",
    granularity=Granularity.PARSHA,
    address_scheme=AddressScheme.STORED,
    shape=(),
    labels=None,
    unit_count=3,
    source="sefaria",
)


def _parsha(seq: int) -> StoredUnitRow:
    return StoredUnitRow(
        seq=seq,
        parent_seq=None,
        addr=(),
        addr_types=("Parasha",),
        granularity=Granularity.PARSHA,
        label_en="Ki Tavo",
        label_he="כי תבוא",
        ordinal=None,
        is_range=True,
        resolved_ref="Deuteronomy 26:1-29:8",
    )


def _aliyah(seq: int, parent: int, ordinal: int) -> StoredUnitRow:
    return StoredUnitRow(
        seq=seq,
        parent_seq=parent,
        addr=(str(ordinal),),
        addr_types=("Aliyah",),
        granularity=Granularity.ALIYAH,
        label_en="Shlishi",
        label_he="שלישי",
        ordinal=ordinal,
        is_range=True,
        resolved_ref="Deuteronomy 26:16-26:19",
    )


async def _seed(session: AsyncSession) -> tuple[Snapshot, object]:
    snapshot = Snapshot(created_at=datetime.now(UTC), sefaria_version="test", unit_count=0, edge_count=0)
    session.add(snapshot)
    await session.flush()
    work = (await persist_works(session, [PARSHA_DRAFT], snapshot.id))[0]
    return snapshot, work


async def test_persist_units_writes_every_row(db_session: AsyncSession) -> None:
    snapshot, work = await _seed(db_session)
    await persist_units(db_session, work, [_parsha(1), _aliyah(2, 1, 3)], snapshot.id)
    found = (await db_session.execute(select(LearnableUnit).order_by(LearnableUnit.seq))).scalars().all()
    assert [u.seq for u in found] == [1, 2]
    assert found[1].resolved_ref == "Deuteronomy 26:16-26:19"
    assert found[1].label_he == "שלישי"


async def test_parent_seq_resolves_to_parent_id(db_session: AsyncSession) -> None:
    snapshot, work = await _seed(db_session)
    await persist_units(db_session, work, [_parsha(1), _aliyah(2, 1, 3)], snapshot.id)
    rows = (await db_session.execute(select(LearnableUnit).order_by(LearnableUnit.seq))).scalars().all()
    assert rows[0].parent_id is None
    assert rows[1].parent_id == rows[0].id


async def test_an_orphan_parent_seq_raises_rather_than_writing_a_null_parent(db_session: AsyncSession) -> None:
    snapshot, work = await _seed(db_session)
    with pytest.raises(ValueError, match="not in this batch"):
        await persist_units(db_session, work, [_aliyah(2, 99, 3)], snapshot.id)


async def test_an_empty_row_list_raises(db_session: AsyncSession) -> None:
    snapshot, work = await _seed(db_session)
    with pytest.raises(ValueError, match="no rows"):
        await persist_units(db_session, work, [], snapshot.id)


async def test_the_pointer_ref_is_built_from_addr_not_from_the_expansion(db_session: AsyncSession) -> None:
    """The stored ref is the pointer; the expansion lives in resolved_ref and is never rebuilt."""
    _, work = await _seed(db_session)
    assert stored_unit_ref(work, _aliyah(2, 1, 3)) == "Parashat HaShavua 3"
    assert stored_unit_ref(work, _parsha(1)) == "Parashat HaShavua"
