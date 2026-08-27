from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.db.models import LearnableUnit, Snapshot, Track, Work
from sidra.ledger.category import Category
from sidra.ledger.locate import ordinal_for_aliyah, ordinal_for_ref
from sidra.ledger.period import Period
from sidra.ledger.track_kind import TrackKind

pytestmark = pytest.mark.integration

ALIYAH_NAMES = ["Rishon", "Sheni", "Shlishi", "Revii", "Chamishi", "Shishi", "Shvii"]


async def _snapshot(session: AsyncSession) -> Snapshot:
    snapshot = Snapshot(created_at=datetime.now(UTC), sefaria_version="test", unit_count=0, edge_count=0)
    session.add(snapshot)
    await session.flush()
    return snapshot


async def _seed_neviim(session: AsyncSession) -> None:
    snapshot = await _snapshot(session)
    for seq, (title, perakim) in enumerate([("Joshua", 24), ("Judges", 21)], start=1):
        session.add(
            Work(
                corpus_id="neviim",
                corpus_seq=seq,
                index_title=title,
                ref_title=title,
                title_he=f"he-{title}",
                granularity=Granularity.PEREK,
                address_scheme=AddressScheme.FLAT,
                shape=[10] * perakim,
                labels=None,
                labels_he=None,
                unit_count=perakim,
                source="sefaria",
                snapshot_id=snapshot.id,
            )
        )
    await session.flush()


async def _seed_parsha_cycle(session: AsyncSession, parshiyos: int) -> None:
    snapshot = await _snapshot(session)
    work = Work(
        corpus_id="torah",
        corpus_seq=100,
        index_title=None,
        ref_title="Parashat HaShavua",
        title_he="פרשת השבוע",
        granularity=Granularity.PARSHA,
        address_scheme=AddressScheme.STORED,
        shape=[],
        labels=None,
        labels_he=None,
        unit_count=parshiyos * 8,
        source="sefaria",
        snapshot_id=snapshot.id,
    )
    session.add(work)
    await session.flush()

    seq = 0
    for parsha in range(1, parshiyos + 1):
        seq += 1
        session.add(
            LearnableUnit(
                work_id=work.id,
                seq=seq,
                ref_title="Parashat HaShavua",
                addr=[],
                addr_types=["Parasha"],
                index_title=None,
                source="sefaria",
                snapshot_id=snapshot.id,
                is_range=True,
                resolved_ref=f"Parsha {parsha} whole",
                granularity=Granularity.PARSHA,
                label_en=f"Parsha{parsha}",
                label_he=f"פרשה{parsha}",
                ordinal=None,
            )
        )
        for ordinal, name in enumerate(ALIYAH_NAMES, start=1):
            seq += 1
            session.add(
                LearnableUnit(
                    work_id=work.id,
                    seq=seq,
                    ref_title="Parashat HaShavua",
                    addr=[str(ordinal)],
                    addr_types=["Aliyah"],
                    index_title=None,
                    source="sefaria",
                    snapshot_id=snapshot.id,
                    is_range=True,
                    resolved_ref=f"Parsha {parsha} aliyah {ordinal}",
                    granularity=Granularity.ALIYAH,
                    label_en=name,
                    label_he=name,
                    ordinal=ordinal,
                )
            )
    await session.flush()


def _track(**overrides: object) -> Track:
    defaults: dict[str, object] = {
        "name_en": "Neviim",
        "name_he": "נביאים",
        "category": Category.DAILY,
        "kind": TrackKind.CORPUS,
        "corpus_id": "neviim",
        "work_ref_title": None,
        "rate": 1,
        "period": Period.DAY,
        "anchor_date": date(2026, 8, 24),
        "anchor_ordinal": 1,
        "is_active": True,
    }
    return Track(**{**defaults, **overrides})  # type: ignore[arg-type]


def _chumash() -> Track:
    return _track(
        name_en="Chumash",
        kind=TrackKind.PARSHA_ALIYAH,
        corpus_id=None,
        work_ref_title="Parashat HaShavua",
    )


# --- ordinal_for_ref ----------------------------------------------------------------------


async def test_a_derived_ref_resolves_to_its_corpus_ordinal(db_session: AsyncSession) -> None:
    await _seed_neviim(db_session)
    assert await ordinal_for_ref(db_session, _track(), "Joshua 1") == 1
    assert await ordinal_for_ref(db_session, _track(), "Joshua 24") == 24
    assert await ordinal_for_ref(db_session, _track(), "Judges 1") == 25


async def test_a_ref_the_track_does_not_hold_raises(db_session: AsyncSession) -> None:
    """A typo must stop the seed rather than place a track in the wrong sefer."""
    await _seed_neviim(db_session)
    with pytest.raises(ValueError, match="'Joshua 99' is not among the track's 45 units"):
        await ordinal_for_ref(db_session, _track(), "Joshua 99")


async def test_a_stored_ref_resolves_through_the_rows(db_session: AsyncSession) -> None:
    """A STORED work answers to Sefaria's own resolved_ref, which no count can produce."""
    await _seed_parsha_cycle(db_session, 3)
    assert await ordinal_for_ref(db_session, _chumash(), "Parsha 1 aliyah 1") == 1
    assert await ordinal_for_ref(db_session, _chumash(), "Parsha 2 aliyah 3") == 10


async def test_a_stored_ref_outside_the_tracks_granularity_is_invisible(db_session: AsyncSession) -> None:
    """The parsha rows are there, but an aliyah-a-day track cannot land on one."""
    await _seed_parsha_cycle(db_session, 3)
    with pytest.raises(ValueError, match="not among the track's 21 units"):
        await ordinal_for_ref(db_session, _chumash(), "Parsha 2 whole")


# --- ordinal_for_aliyah -------------------------------------------------------------------


async def test_a_parsha_and_aliyah_resolve_to_an_ordinal(db_session: AsyncSession) -> None:
    await _seed_parsha_cycle(db_session, 3)
    assert await ordinal_for_aliyah(db_session, _chumash(), "Parsha1", 1) == 1
    assert await ordinal_for_aliyah(db_session, _chumash(), "Parsha1", 7) == 7
    assert await ordinal_for_aliyah(db_session, _chumash(), "Parsha2", 1) == 8
    assert await ordinal_for_aliyah(db_session, _chumash(), "Parsha3", 3) == 17


@pytest.mark.parametrize("aliyah", [0, 8, -1])
async def test_an_aliyah_number_outside_one_to_seven_raises(db_session: AsyncSession, aliyah: int) -> None:
    await _seed_parsha_cycle(db_session, 1)
    with pytest.raises(ValueError, match="aliyah must be 1..7"):
        await ordinal_for_aliyah(db_session, _chumash(), "Parsha1", aliyah)


async def test_an_unknown_parsha_raises_naming_the_count(db_session: AsyncSession) -> None:
    await _seed_parsha_cycle(db_session, 2)
    with pytest.raises(ValueError, match="no aliyah 3 of 'Vayeilech' among the track's 14 aliyot"):
        await ordinal_for_aliyah(db_session, _chumash(), "Vayeilech", 3)
