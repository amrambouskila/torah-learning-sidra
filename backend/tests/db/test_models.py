from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.db.models import LearnableUnit, Snapshot, TitleAlias, TopicLink, Work

pytestmark = pytest.mark.integration

AVODAH_ZARAH_HE = "עבודה זרה"


async def _snapshot(session: AsyncSession) -> Snapshot:
    snapshot = Snapshot(
        created_at=datetime.now(UTC),
        sefaria_version="2026-08-24",
        unit_count=0,
        edge_count=0,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


async def _work(session: AsyncSession, snapshot: Snapshot, **overrides: object) -> Work:
    defaults: dict[str, object] = {
        "corpus_id": "bavli",
        "corpus_seq": 25,
        "index_title": "Avodah Zarah",
        "ref_title": "Avodah Zarah",
        "title_he": AVODAH_ZARAH_HE,
        "granularity": Granularity.DAF_AMUD,
        "address_scheme": AddressScheme.DAF_AMUD,
        "shape": [0, 0, 8, 18],
        "labels": None,
        "unit_count": 2,
        "source": "sefaria",
        "snapshot_id": snapshot.id,
    }
    work = Work(**{**defaults, **overrides})  # type: ignore[arg-type]
    session.add(work)
    await session.flush()
    return work


async def test_snapshot_round_trips(db_session: AsyncSession) -> None:
    snapshot = await _snapshot(db_session)
    found = (await db_session.execute(select(Snapshot).where(Snapshot.id == snapshot.id))).scalar_one()
    assert found.sefaria_version == "2026-08-24"
    assert isinstance(found.id, uuid.UUID)
    assert found.created_at.tzinfo is not None


async def test_work_round_trips_with_its_shape_array(db_session: AsyncSession) -> None:
    snapshot = await _snapshot(db_session)
    work = await _work(db_session, snapshot, shape=[0, 0, 8, 18, 13], unit_count=3)
    found = (await db_session.execute(select(Work).where(Work.id == work.id))).scalar_one()
    assert found.shape == [0, 0, 8, 18, 13]
    assert found.title_he == AVODAH_ZARAH_HE
    assert found.address_scheme is AddressScheme.DAF_AMUD
    assert found.granularity is Granularity.DAF_AMUD
    assert found.labels is None


async def test_work_labels_survive_jsonb_round_tripping(db_session: AsyncSession) -> None:
    """Orchot Tzadikim's gate names ride on the work, not on rows."""
    snapshot = await _snapshot(db_session)
    gates = ["ON TORAH", "ON HUMILITY", "ON REMORSE"]
    work = await _work(
        db_session,
        snapshot,
        corpus_id="mussar",
        corpus_seq=1,
        ref_title="Orchot Tzadikim",
        index_title="Orchot Tzadikim",
        title_he="אורחות צדיקים",
        granularity=Granularity.GATE,
        address_scheme=AddressScheme.FLAT,
        shape=[11, 9, 11],
        labels=gates,
        unit_count=3,
    )
    found = (await db_session.execute(select(Work).where(Work.id == work.id))).scalar_one()
    assert found.labels == gates


async def test_learnable_unit_stores_addr_and_hebrew(db_session: AsyncSession) -> None:
    snapshot = await _snapshot(db_session)
    work = await _work(
        db_session,
        snapshot,
        corpus_id="torah",
        corpus_seq=5,
        ref_title="Deuteronomy, Ki Tavo",
        granularity=Granularity.ALIYAH,
        address_scheme=AddressScheme.STORED,
        title_he="כי תבוא",
    )
    unit = LearnableUnit(
        work_id=work.id,
        seq=3,
        ref_title="Deuteronomy, Ki Tavo",
        addr=["3"],
        addr_types=["Aliyah"],
        index_title="Deuteronomy",
        source="sefaria",
        snapshot_id=snapshot.id,
        is_range=True,
        resolved_ref="Deuteronomy 26:16-26:19",
        resolved_he_ref="דברים כ״ו:ט״ז-י״ט",
        granularity=Granularity.ALIYAH,
        label_en="Shlishi",
        label_he="שלישי",
        ordinal=3,
    )
    db_session.add(unit)
    await db_session.flush()

    found = (await db_session.execute(select(LearnableUnit).where(LearnableUnit.seq == 3))).scalar_one()
    assert found.addr == ["3"]
    assert found.addr_types == ["Aliyah"]
    assert found.label_he == "שלישי"
    assert found.resolved_ref == "Deuteronomy 26:16-26:19"
    assert found.is_range is True


async def test_title_alias_round_trips(db_session: AsyncSession) -> None:
    snapshot = await _snapshot(db_session)
    work = await _work(db_session, snapshot)
    db_session.add(TitleAlias(work_id=work.id, alias="Mesechet Avoda Zara", lang="en", source="local"))
    await db_session.flush()
    found = (await db_session.execute(select(TitleAlias).where(TitleAlias.alias == "Mesechet Avoda Zara"))).scalar_one()
    assert found.lang == "en"
    assert found.work_id == work.id


async def test_topic_link_round_trips(db_session: AsyncSession) -> None:
    snapshot = await _snapshot(db_session)
    link = TopicLink(
        from_ref="Mishneh Torah, Human Dispositions 5:8",
        to_ref="Shulchan Arukh, Orach Chayim 2:6",
        from_category="Halakhah",
        to_category="Halakhah",
        kind="ein_mishpat",
        anchor_group="Mishneh Torah, Human Dispositions 5:8",
        confidence="direct",
        snapshot_id=snapshot.id,
    )
    db_session.add(link)
    await db_session.flush()
    found = (
        await db_session.execute(select(TopicLink).where(TopicLink.to_ref == "Shulchan Arukh, Orach Chayim 2:6"))
    ).scalar_one()
    assert found.kind == "ein_mishpat"
    assert found.confidence == "direct"
