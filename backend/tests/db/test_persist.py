from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.catalog.work_draft import WorkDraft
from sidra.db.models import Snapshot, Work
from sidra.db.persist import persist_works

pytestmark = pytest.mark.integration


def _draft(seq: int, title: str, shape: tuple[int, ...], **overrides: object) -> WorkDraft:
    defaults: dict[str, object] = {
        "corpus_id": "neviim",
        "corpus_seq": seq,
        "index_title": title,
        "ref_title": title,
        "title_he": "ירמיהו",
        "granularity": Granularity.PEREK,
        "address_scheme": AddressScheme.FLAT,
        "shape": shape,
        "labels": None,
        "unit_count": len(shape),
        "source": "sefaria",
    }
    return WorkDraft(**{**defaults, **overrides})  # type: ignore[arg-type]


async def _snapshot(session: AsyncSession) -> Snapshot:
    snapshot = Snapshot(created_at=datetime.now(UTC), sefaria_version="test", unit_count=0, edge_count=0)
    session.add(snapshot)
    await session.flush()
    return snapshot


async def test_persist_works_writes_every_draft(db_session: AsyncSession) -> None:
    snapshot = await _snapshot(db_session)
    works = await persist_works(
        db_session,
        [_draft(1, "Joshua", (18, 24)), _draft(2, "Judges", (36, 23, 31))],
        snapshot.id,
    )
    assert len(works) == 2
    found = (await db_session.execute(select(Work).order_by(Work.corpus_seq))).scalars().all()
    assert [w.ref_title for w in found] == ["Joshua", "Judges"]
    assert [w.corpus_seq for w in found] == [1, 2]


async def test_the_shape_array_survives_jsonb_round_tripping(db_session: AsyncSession) -> None:
    snapshot = await _snapshot(db_session)
    await persist_works(db_session, [_draft(1, "Nazir", (0, 0, 8, 0, 12))], snapshot.id)
    found = (await db_session.execute(select(Work).where(Work.ref_title == "Nazir"))).scalar_one()
    assert found.shape == [0, 0, 8, 0, 12]


async def test_labels_survive_jsonb_round_tripping(db_session: AsyncSession) -> None:
    snapshot = await _snapshot(db_session)
    gates = ("ON TORAH", "ON HUMILITY")
    await persist_works(
        db_session,
        [_draft(1, "Orchot Tzadikim", (11, 9), corpus_id="mussar", labels=gates, granularity=Granularity.GATE)],
        snapshot.id,
    )
    found = (await db_session.execute(select(Work).where(Work.ref_title == "Orchot Tzadikim"))).scalar_one()
    assert found.labels == list(gates)


async def test_a_duplicate_corpus_position_is_rejected(db_session: AsyncSession) -> None:
    """Two works cannot occupy the same slot in a corpus."""
    snapshot = await _snapshot(db_session)
    with pytest.raises(IntegrityError):
        await persist_works(db_session, [_draft(1, "Joshua", (18,)), _draft(1, "Judges", (36,))], snapshot.id)
    # The failed flush poisons the transaction; roll back so the fixture teardown is clean.
    await db_session.rollback()


async def test_an_empty_draft_list_raises(db_session: AsyncSession) -> None:
    """A corpus that ingests to nothing is a failure, not a no-op."""
    snapshot = await _snapshot(db_session)
    with pytest.raises(ValueError, match="no drafts"):
        await persist_works(db_session, [], snapshot.id)
