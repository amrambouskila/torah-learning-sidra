from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.db.models import LearnableUnit, Snapshot, Track, Work
from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.position import position_at, track_total
from sidra.ledger.track_kind import TrackKind

pytestmark = pytest.mark.integration

AVODAH_ZARAH_SHAPE = [0 if index in {0, 1} else 7 for index in range(152)]
# Joshua 24, Judges 21, I Samuel 31, Jeremiah 52 -- a stand-in Neviim corpus in canonical order.
NEVIIM = [("Joshua", "יהושע", 24), ("Judges", "שופטים", 21), ("I Samuel", "שמואל א", 31), ("Jeremiah", "ירמיהו", 52)]


async def _snapshot(session: AsyncSession) -> Snapshot:
    snapshot = Snapshot(created_at=datetime.now(UTC), sefaria_version="test", unit_count=0, edge_count=0)
    session.add(snapshot)
    await session.flush()
    return snapshot


async def _seed_neviim(session: AsyncSession) -> None:
    snapshot = await _snapshot(session)
    for seq, (title, title_he, perakim) in enumerate(NEVIIM, start=1):
        session.add(
            Work(
                corpus_id="neviim",
                corpus_seq=seq,
                index_title=title,
                ref_title=title,
                title_he=title_he,
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


async def test_the_first_ordinal_is_the_first_work(db_session: AsyncSession) -> None:
    await _seed_neviim(db_session)
    position = await position_at(db_session, _track(), 1)
    assert position.work_ref_title == "Joshua"
    assert position.ref == "Joshua 1"
    assert position.seq_in_work == 1


async def test_a_corpus_track_streams_across_works(db_session: AsyncSession) -> None:
    """The point of a corpus track: after the last perek of one book comes the first of the next."""
    await _seed_neviim(db_session)
    track = _track()
    assert (await position_at(db_session, track, 24)).ref == "Joshua 24"
    assert (await position_at(db_session, track, 25)).ref == "Judges 1"
    assert (await position_at(db_session, track, 45)).ref == "Judges 21"
    assert (await position_at(db_session, track, 46)).ref == "I Samuel 1"


async def test_the_real_neviim_position_resolves(db_session: AsyncSession) -> None:
    await _seed_neviim(db_session)
    ordinal = 24 + 21 + 31 + 44
    position = await position_at(db_session, _track(), ordinal)
    assert position.ref == "Jeremiah 44"
    assert position.work_title_he == "ירמיהו"
    assert position.label_he == "מ״ד"
    assert position.corpus_ordinal == ordinal


async def test_the_last_ordinal_is_the_final_unit(db_session: AsyncSession) -> None:
    await _seed_neviim(db_session)
    total = await track_total(db_session, _track())
    assert total == sum(perakim for _, _, perakim in NEVIIM)
    assert (await position_at(db_session, _track(), total)).ref == "Jeremiah 52"


async def test_an_ordinal_past_the_end_raises_naming_the_total(db_session: AsyncSession) -> None:
    await _seed_neviim(db_session)
    total = await track_total(db_session, _track())
    with pytest.raises(ValueError, match=f"holds {total} units"):
        await position_at(db_session, _track(), total + 1)


@pytest.mark.parametrize("ordinal", [0, -1])
async def test_a_non_positive_ordinal_raises(db_session: AsyncSession, ordinal: int) -> None:
    await _seed_neviim(db_session)
    with pytest.raises(ValueError, match="at least 1"):
        await position_at(db_session, _track(), ordinal)


async def test_a_curated_queue_track_runs_within_one_work(db_session: AsyncSession) -> None:
    """Gemara learns one masechta at a time, so its ordinal is inside the current work."""
    snapshot = await _snapshot(db_session)
    db_session.add(
        Work(
            corpus_id="bavli",
            corpus_seq=1,
            index_title="Avodah Zarah",
            ref_title="Avodah Zarah",
            title_he="עבודה זרה",
            granularity=Granularity.DAF_AMUD,
            address_scheme=AddressScheme.DAF_AMUD,
            shape=AVODAH_ZARAH_SHAPE,
            labels=None,
            labels_he=None,
            unit_count=150,
            source="sefaria",
            snapshot_id=snapshot.id,
        )
    )
    await db_session.flush()

    track = _track(name_en="Gemara", kind=TrackKind.CURATED_QUEUE, corpus_id=None, work_ref_title="Avodah Zarah")
    assert await track_total(db_session, track) == 150
    assert (await position_at(db_session, track, 1)).ref == "Avodah Zarah 2a"

    from sidra.catalog.bavli_amudim import real_amudim

    amudim = real_amudim(AVODAH_ZARAH_SHAPE)
    actual, scheduled = amudim.index("28b") + 1, amudim.index("38b") + 1
    assert (await position_at(db_session, track, actual)).ref == "Avodah Zarah 28b"
    assert (await position_at(db_session, track, actual)).label_he == "כ״ח ע״ב"
    assert (await position_at(db_session, track, scheduled)).ref == "Avodah Zarah 38b"
    assert scheduled - actual == 20


async def test_a_stored_work_resolves_through_its_rows(db_session: AsyncSession) -> None:
    """Aliyot carry Sefaria's own range expansion, which the spec forbids rebuilding."""
    snapshot = await _snapshot(db_session)
    work = Work(
        corpus_id="torah",
        corpus_seq=1,
        index_title=None,
        ref_title="Parashat HaShavua",
        title_he="פרשת השבוע",
        granularity=Granularity.PARSHA,
        address_scheme=AddressScheme.STORED,
        shape=[],
        labels=None,
        labels_he=None,
        unit_count=2,
        source="sefaria",
        snapshot_id=snapshot.id,
    )
    db_session.add(work)
    await db_session.flush()
    db_session.add(
        LearnableUnit(
            work_id=work.id,
            seq=1,
            ref_title="Parashat HaShavua",
            addr=["3"],
            addr_types=["Aliyah"],
            index_title=None,
            source="sefaria",
            snapshot_id=snapshot.id,
            is_range=True,
            resolved_ref="Deuteronomy 26:16-26:19",
            granularity=Granularity.ALIYAH,
            label_en="Shlishi",
            label_he="שלישי",
            ordinal=3,
        )
    )
    await db_session.flush()

    track = _track(name_en="Chumash", kind=TrackKind.PARSHA_ALIYAH, corpus_id=None, work_ref_title="Parashat HaShavua")
    position = await position_at(db_session, track, 1)
    assert position.ref == "Deuteronomy 26:16-26:19"
    assert position.label_en == "Shlishi"
    assert position.label_he == "שלישי"


async def test_a_stored_work_with_no_rows_holds_nothing(db_session: AsyncSession) -> None:
    snapshot = await _snapshot(db_session)
    work = Work(
        corpus_id="torah",
        corpus_seq=1,
        index_title=None,
        ref_title="Parashat HaShavua",
        title_he="פרשת השבוע",
        granularity=Granularity.PARSHA,
        address_scheme=AddressScheme.STORED,
        shape=[],
        labels=None,
        labels_he=None,
        unit_count=2,
        source="sefaria",
        snapshot_id=snapshot.id,
    )
    db_session.add(work)
    await db_session.flush()
    # The declared unit_count is metadata; what the track can reach is the rows that exist.
    track = _track(name_en="Chumash", kind=TrackKind.PARSHA_ALIYAH, corpus_id=None, work_ref_title="Parashat HaShavua")
    assert await track_total(db_session, track) == 0
    with pytest.raises(ValueError, match="holds 0 units"):
        await position_at(db_session, track, 1)


async def test_a_corpus_track_without_a_corpus_raises(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="must name a corpus"):
        await position_at(db_session, _track(corpus_id=None), 1)


async def test_a_single_work_track_without_a_work_raises(db_session: AsyncSession) -> None:
    track = _track(kind=TrackKind.CURATED_QUEUE, corpus_id=None, work_ref_title=None)
    with pytest.raises(ValueError, match="must name a work"):
        await position_at(db_session, track, 1)


async def test_a_track_naming_a_missing_work_raises(db_session: AsyncSession) -> None:
    track = _track(kind=TrackKind.CURATED_QUEUE, corpus_id=None, work_ref_title="Nonesuch")
    with pytest.raises(ValueError, match="is in the catalog"):
        await position_at(db_session, track, 1)


async def _seed_parsha_cycle(session: AsyncSession, parshiyos: int) -> Work:
    """Parashat HaShavua as it really is: each parsha row followed by its seven aliyot."""
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

    aliyah_names = ["Rishon", "Sheni", "Shlishi", "Revii", "Chamishi", "Shishi", "Shvii"]
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
        for ordinal, name in enumerate(aliyah_names, start=1):
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
    return work


def _chumash() -> Track:
    return _track(
        name_en="Chumash",
        kind=TrackKind.PARSHA_ALIYAH,
        corpus_id=None,
        work_ref_title="Parashat HaShavua",
    )


async def test_an_aliyah_track_never_lands_on_a_parsha_row(db_session: AsyncSession) -> None:
    """The rows interleave, so indexing them directly would hit a parsha every eighth day."""
    await _seed_parsha_cycle(db_session, 3)
    refs = [(await position_at(db_session, _chumash(), n)).ref for n in range(1, 15)]
    assert refs[:7] == [f"Parsha 1 aliyah {n}" for n in range(1, 8)]
    assert refs[7:] == [f"Parsha 2 aliyah {n}" for n in range(1, 8)]
    assert all("whole" not in ref for ref in refs)


async def test_an_aliyah_track_counts_only_the_aliyot(db_session: AsyncSession) -> None:
    """Fifty-four parshiyos is 378 aliyot, not the 432 rows the work holds."""
    await _seed_parsha_cycle(db_session, 54)
    assert await track_total(db_session, _chumash()) == 378


async def test_the_eighth_aliyah_opens_the_next_parsha(db_session: AsyncSession) -> None:
    await _seed_parsha_cycle(db_session, 2)
    position = await position_at(db_session, _chumash(), 8)
    assert position.label_en == "Rishon"
    assert position.ref == "Parsha 2 aliyah 1"


async def test_an_aliyah_ordinal_past_the_cycle_raises(db_session: AsyncSession) -> None:
    await _seed_parsha_cycle(db_session, 2)
    with pytest.raises(ValueError, match="holds 14 units"):
        await position_at(db_session, _chumash(), 15)


async def _seed_complex_work(
    session: AsyncSession, parent: str, parts: list[tuple[str, int]], *, corpus_id: str = "chassidus"
) -> None:
    """Sefaria splits a complex work into parts titled '<parent>, <part>'."""
    snapshot = await _snapshot(session)
    for seq, (part, perakim) in enumerate(parts, start=1):
        session.add(
            Work(
                corpus_id=corpus_id,
                corpus_seq=seq,
                index_title=f"{parent}, {part}",
                ref_title=f"{parent}, {part}",
                title_he=f"he-{part}",
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


async def test_naming_a_complex_work_takes_its_parts_in_order(db_session: AsyncSession) -> None:
    """There is no `Tanya` in the catalog, only its five chalakim -- but Tanya is one track."""
    await _seed_complex_work(db_session, "Tanya", [("Part I; Likkutei Amarim", 53), ("Part II; Shaar", 12)])
    track = _track(name_en="Tanya", kind=TrackKind.CURATED_QUEUE, corpus_id=None, work_ref_title="Tanya")
    assert await track_total(db_session, track) == 65
    assert (await position_at(db_session, track, 1)).ref == "Tanya, Part I; Likkutei Amarim 1"
    assert (await position_at(db_session, track, 54)).ref == "Tanya, Part II; Shaar 1"


async def test_a_part_can_still_be_named_on_its_own(db_session: AsyncSession) -> None:
    await _seed_complex_work(db_session, "Tanya", [("Part I; Likkutei Amarim", 53), ("Part II; Shaar", 12)])
    track = _track(
        name_en="Tanya I",
        kind=TrackKind.CURATED_QUEUE,
        corpus_id=None,
        work_ref_title="Tanya, Part I; Likkutei Amarim",
    )
    assert await track_total(db_session, track) == 53


async def test_a_sibling_sharing_a_word_is_not_swept_in(db_session: AsyncSession) -> None:
    """The match is on '<parent>, ', so `Tanya Commentary` never joins the Tanya track."""
    await _seed_complex_work(db_session, "Tanya", [("Part I; Likkutei Amarim", 53)])
    await _seed_complex_work(db_session, "Tanya Commentary", [("Part I", 9)], corpus_id="mussar")
    track = _track(name_en="Tanya", kind=TrackKind.CURATED_QUEUE, corpus_id=None, work_ref_title="Tanya")
    assert await track_total(db_session, track) == 53
