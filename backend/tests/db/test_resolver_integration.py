from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.bavli_amudim import real_amudim
from sidra.catalog.granularity import Granularity
from sidra.catalog.resolve import unit_at, unit_count
from sidra.db.models import Snapshot, Work

pytestmark = pytest.mark.integration

# Avodah Zarah as Sefaria reports it: 152 slots, indices 0 and 1 empty, 150 real amudim.
AVODAH_ZARAH_SHAPE = [0 if index in {0, 1} else 7 for index in range(152)]


async def test_the_derived_catalog_works_end_to_end(db_session: AsyncSession) -> None:
    """One database row and 152 integers stand in for 150 units.

    This is the test that proves spec section 7.10. If it passes, the catalog does not need the
    ~25,000 unit rows the original design called for.
    """
    snapshot = Snapshot(created_at=datetime.now(UTC), sefaria_version="2026-08-24", unit_count=150, edge_count=0)
    db_session.add(snapshot)
    await db_session.flush()

    db_session.add(
        Work(
            corpus_id="bavli",
            corpus_seq=25,
            index_title="Avodah Zarah",
            ref_title="Avodah Zarah",
            title_he="עבודה זרה",
            granularity=Granularity.DAF_AMUD,
            address_scheme=AddressScheme.DAF_AMUD,
            shape=AVODAH_ZARAH_SHAPE,
            labels=None,
            unit_count=unit_count(AddressScheme.DAF_AMUD, AVODAH_ZARAH_SHAPE),
            source="sefaria",
            snapshot_id=snapshot.id,
        )
    )
    await db_session.flush()
    db_session.expunge_all()

    work = (await db_session.execute(select(Work).where(Work.ref_title == "Avodah Zarah"))).scalar_one()
    assert work.unit_count == 150

    amudim = real_amudim(work.shape)
    actual = amudim.index("28b") + 1
    scheduled = amudim.index("38b") + 1

    assert unit_at(work.ref_title, work.address_scheme, work.shape, actual).ref == "Avodah Zarah 28b"
    assert unit_at(work.ref_title, work.address_scheme, work.shape, scheduled).ref == "Avodah Zarah 38b"
    assert scheduled - actual == 20

    assert unit_at(work.ref_title, work.address_scheme, work.shape, actual).label_he == "כ״ח ע״ב"
    assert unit_at(work.ref_title, work.address_scheme, work.shape, 1).ref == "Avodah Zarah 2a"
    assert unit_at(work.ref_title, work.address_scheme, work.shape, 150).ref == "Avodah Zarah 76b"
