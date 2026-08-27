from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.alignment.ein_mishpat import EinMishpatEdge
from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.catalog.ingest_aliases import AliasRow
from sidra.catalog.resolve import unit_at
from sidra.catalog.snapshot import FORMAT_VERSION, SnapshotPayload
from sidra.catalog.stored_unit import StoredUnitRow
from sidra.catalog.work_draft import WorkDraft
from sidra.db.models import LearnableUnit, Snapshot, TitleAlias, TopicLink, Work
from sidra.db.seed import catalog_is_empty, seed_from_snapshot

pytestmark = pytest.mark.integration

AVODAH_ZARAH_SHAPE = tuple(0 if index in {0, 1} else 7 for index in range(152))

PAYLOAD = SnapshotPayload(
    format_version=FORMAT_VERSION,
    created_at=datetime(2026, 8, 25, 12, 0, tzinfo=UTC),
    sefaria_version="2026-08-25",
    works=(
        WorkDraft(
            corpus_id="bavli",
            corpus_seq=1,
            index_title="Avodah Zarah",
            ref_title="Avodah Zarah",
            title_he="עבודה זרה",
            granularity=Granularity.DAF_AMUD,
            address_scheme=AddressScheme.DAF_AMUD,
            shape=AVODAH_ZARAH_SHAPE,
            labels=None,
            unit_count=150,
            source="sefaria",
        ),
        WorkDraft(
            corpus_id="torah",
            corpus_seq=1,
            index_title=None,
            ref_title="Parashat HaShavua",
            title_he="פרשת השבוע",
            granularity=Granularity.PARSHA,
            address_scheme=AddressScheme.STORED,
            shape=(),
            labels=None,
            unit_count=2,
            source="sefaria",
        ),
    ),
    units=(
        (
            "Parashat HaShavua",
            StoredUnitRow(
                seq=1,
                parent_seq=None,
                addr=(),
                addr_types=("Parasha",),
                granularity=Granularity.PARSHA,
                label_en="Ki Tavo",
                label_he="כי תבוא",
                ordinal=None,
                is_range=True,
                resolved_ref="Deuteronomy 26:1-29:8",
            ),
        ),
        (
            "Parashat HaShavua",
            StoredUnitRow(
                seq=2,
                parent_seq=1,
                addr=("3",),
                addr_types=("Aliyah",),
                granularity=Granularity.ALIYAH,
                label_en="Shlishi",
                label_he="שלישי",
                ordinal=3,
                is_range=True,
                resolved_ref="Deuteronomy 26:16-26:19",
            ),
        ),
    ),
    aliases=(AliasRow(ref_title="Avodah Zarah", alias="Mesechet Avoda Zara", lang="en", source="local"),),
    links=(
        EinMishpatEdge("Avodah Zarah 38b:4", "Mishneh Torah, Forbidden Foods 17:13", "Talmud", "Halakhah"),
        EinMishpatEdge("Avodah Zarah 38b:4", "Tur, Yoreh De'ah 112", "Talmud", "Halakhah"),
    ),
    bridged=(EinMishpatEdge("Avodah Zarah 38b:4", "Shulchan Arukh, Yoreh De'ah 112", "Talmud", "Halakhah"),),
)


async def test_seeding_writes_every_table(db_session: AsyncSession) -> None:
    counts = await seed_from_snapshot(db_session, PAYLOAD)
    assert counts.works == 2
    assert counts.units == 2
    assert counts.aliases == 1
    assert counts.links == 3
    assert await db_session.scalar(select(func.count()).select_from(Work)) == 2
    assert await db_session.scalar(select(func.count()).select_from(LearnableUnit)) == 2
    assert await db_session.scalar(select(func.count()).select_from(TitleAlias)) == 1
    assert await db_session.scalar(select(func.count()).select_from(TopicLink)) == 3
    assert await db_session.scalar(select(func.count()).select_from(Snapshot)) == 1


async def test_seeding_twice_is_idempotent(db_session: AsyncSession) -> None:
    """Doubles would be worse than a failure: the catalog would look plausible and be wrong."""
    first = await seed_from_snapshot(db_session, PAYLOAD)
    second = await seed_from_snapshot(db_session, PAYLOAD)
    assert first == second
    assert await db_session.scalar(select(func.count()).select_from(Work)) == 2
    assert await db_session.scalar(select(func.count()).select_from(TopicLink)) == 3
    assert await db_session.scalar(select(func.count()).select_from(Snapshot)) == 1


async def test_the_seeded_work_resolves_its_units(db_session: AsyncSession) -> None:
    """The end-to-end point of the derived catalog: one row, 150 units."""
    await seed_from_snapshot(db_session, PAYLOAD)
    work = (await db_session.execute(select(Work).where(Work.ref_title == "Avodah Zarah"))).scalar_one()
    assert work.unit_count == 150
    from sidra.catalog.bavli_amudim import real_amudim

    amudim = real_amudim(work.shape)
    actual, scheduled = amudim.index("28b") + 1, amudim.index("38b") + 1
    assert scheduled - actual == 20
    assert unit_at(work.ref_title, work.address_scheme, work.shape, actual).ref == "Avodah Zarah 28b"


async def test_stored_units_keep_their_parent_and_expansion(db_session: AsyncSession) -> None:
    await seed_from_snapshot(db_session, PAYLOAD)
    rows = (await db_session.execute(select(LearnableUnit).order_by(LearnableUnit.seq))).scalars().all()
    assert rows[1].parent_id == rows[0].id
    assert rows[1].resolved_ref == "Deuteronomy 26:16-26:19"
    assert rows[1].label_he == "שלישי"


async def test_units_for_an_unknown_work_raise(db_session: AsyncSession) -> None:
    import dataclasses

    broken = dataclasses.replace(PAYLOAD, units=(("Nonesuch", PAYLOAD.units[0][1]),))
    with pytest.raises(ValueError, match="not among its works"):
        await seed_from_snapshot(db_session, broken)


async def test_catalog_is_empty_before_and_after(db_session: AsyncSession) -> None:
    assert await catalog_is_empty(db_session) is True
    await seed_from_snapshot(db_session, PAYLOAD)
    assert await catalog_is_empty(db_session) is False


async def test_bridged_edges_are_marked_inferred_not_direct(db_session: AsyncSession) -> None:
    """An inference through Tur must never be indistinguishable from the apparatus itself."""
    await seed_from_snapshot(db_session, PAYLOAD)
    rows = (await db_session.execute(select(TopicLink))).scalars().all()
    by_kind = {row.kind: row for row in rows}
    assert by_kind["ein_mishpat"].confidence == "direct"
    assert by_kind["tur_bridge"].confidence == "inferred"
    assert by_kind["tur_bridge"].to_ref.startswith("Shulchan Arukh, ")
