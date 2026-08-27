from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.calendar.calendar_day import CalendarDay
from sidra.calendar.store import store_calendar
from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.db.models import Advance, Chavrusa, LearnableUnit, Snapshot, Tag, Track, Work, track_tag
from sidra.ledger.seed_tracks import actual_ordinal, clear_ledger, ledger_is_empty, seed_tracks
from sidra.ledger.tracks_file import parse_tracks_file

pytestmark = pytest.mark.integration

AS_OF = date(2026, 8, 24)
HEBREW_AS_OF = "י״א בֶּאֱלוּל תשפ״ו"

TRACKS_YAML = """
as_of: 2026-08-24
tags:
  - name: parsha
    name_he: פרשה
    color: "#8a6d3b"
chavrusas:
  - name: David Hadar
tracks:
  - name_en: Neviim
    name_he: נביאים
    category: daily
    kind: corpus
    corpus_id: neviim
    rate: 1
    period: day
    scheduled_ref: Jeremiah 47
    current_ref: Jeremiah 44
  - name_en: Chumash
    name_he: חומש
    category: daily
    kind: parsha_aliyah
    work_ref_title: Parashat HaShavua
    rate: 1
    period: day
    current_aliyah: {parsha: Parsha2, aliyah: 3}
    tags: [parsha]
  - name_en: Likutei Sichot
    name_he: ליקוטי שיחות
    category: shabbat
    kind: parsha_weekly
    work_ref_title: Likutei Sichot
    rate: 1
    period: week
    starts_on: 2026-10-10
    tags: [parsha]
  - name_en: David Hadar — Brachot
    name_he: דוד הדר
    category: chavrusa
    kind: curated_queue
    work_ref_title: Berakhot
    period: none
    chavrusa: David Hadar
    current_ref: Berakhot 13a
"""

NEVIIM = [("Joshua", 24), ("Judges", 21), ("I Samuel", 31), ("Jeremiah", 52)]
BERAKHOT_SHAPE = [0 if index in {0, 1} else 7 for index in range(128)]
ALIYAH_NAMES = ["Rishon", "Sheni", "Shlishi", "Revii", "Chamishi", "Shishi", "Shvii"]


async def _catalog(session: AsyncSession) -> None:
    """A miniature of the real catalog: a corpus, a daf-amud work, a parsha cycle, a local work."""
    snapshot = Snapshot(created_at=datetime.now(UTC), sefaria_version="test", unit_count=0, edge_count=0)
    session.add(snapshot)
    await session.flush()

    def work(**kwargs: object) -> Work:
        base: dict[str, object] = {
            "index_title": None,
            "labels": None,
            "labels_he": None,
            "source": "sefaria",
            "snapshot_id": snapshot.id,
        }
        return Work(**{**base, **kwargs})  # type: ignore[arg-type]

    for seq, (title, perakim) in enumerate(NEVIIM, start=1):
        session.add(
            work(
                corpus_id="neviim",
                corpus_seq=seq,
                ref_title=title,
                title_he=f"he-{title}",
                granularity=Granularity.PEREK,
                address_scheme=AddressScheme.FLAT,
                shape=[10] * perakim,
                unit_count=perakim,
            )
        )
    session.add(
        work(
            corpus_id="bavli",
            corpus_seq=1,
            ref_title="Berakhot",
            title_he="ברכות",
            granularity=Granularity.DAF_AMUD,
            address_scheme=AddressScheme.DAF_AMUD,
            shape=BERAKHOT_SHAPE,
            unit_count=126,
        )
    )
    # A second masechta, so a track over one of them is visibly part of a wider Shas.
    session.add(
        work(
            corpus_id="bavli",
            corpus_seq=2,
            ref_title="Shabbat",
            title_he="שבת",
            granularity=Granularity.DAF_AMUD,
            address_scheme=AddressScheme.DAF_AMUD,
            shape=[0, 0, *([10] * 30)],
            unit_count=60,
        )
    )
    session.add(
        work(
            corpus_id="parsha_weekly",
            corpus_seq=1,
            ref_title="Likutei Sichot",
            title_he="ליקוטי שיחות",
            granularity=Granularity.PARSHA,
            address_scheme=AddressScheme.FLAT,
            shape=[1] * 54,
            unit_count=54,
            source="local",
        )
    )

    parsha_work = work(
        corpus_id="torah",
        corpus_seq=100,
        ref_title="Parashat HaShavua",
        title_he="פרשת השבוע",
        granularity=Granularity.PARSHA,
        address_scheme=AddressScheme.STORED,
        shape=[],
        unit_count=24,
    )
    session.add(parsha_work)
    await session.flush()

    seq = 0
    for parsha in range(1, 4):
        seq += 1
        session.add(
            LearnableUnit(
                work_id=parsha_work.id,
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
                    work_id=parsha_work.id,
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


async def _calendar(session: AsyncSession) -> None:
    await store_calendar(
        session,
        [
            CalendarDay(
                civil_date=AS_OF,
                hebrew_date=HEBREW_AS_OF,
                parsha_en=("Ki Tavo",),
                parsha_he=("כי תבוא",),
                is_yom_tov=False,
            )
        ],
    )


async def _seed(session: AsyncSession) -> object:
    await _catalog(session)
    await _calendar(session)
    return await seed_tracks(session, parse_tracks_file(TRACKS_YAML))


async def _track(session: AsyncSession, name: str) -> Track:
    return (await session.execute(select(Track).where(Track.name_en == name))).scalar_one()


async def test_the_seed_writes_every_track_tag_and_chavrusa(db_session: AsyncSession) -> None:
    counts = await _seed(db_session)
    assert (counts.tracks, counts.tags, counts.chavrusas) == (4, 1, 1)  # type: ignore[attr-defined]
    assert await db_session.scalar(select(func.count()).select_from(Track)) == 4
    assert await db_session.scalar(select(func.count()).select_from(Tag)) == 1
    assert await db_session.scalar(select(func.count()).select_from(Chavrusa)) == 1


async def test_a_scheduled_ref_becomes_the_anchor(db_session: AsyncSession) -> None:
    """Jeremiah 47 is the 123rd perek of the corpus; the anchor lands exactly there."""
    await _seed(db_session)
    track = await _track(db_session, "Neviim")
    assert track.anchor_date == AS_OF
    assert track.anchor_ordinal == 24 + 21 + 31 + 47


async def test_a_current_ref_becomes_the_opening_advance(db_session: AsyncSession) -> None:
    await _seed(db_session)
    track = await _track(db_session, "Neviim")
    assert await actual_ordinal(db_session, track) == 24 + 21 + 31 + 44


async def test_the_gap_between_them_is_the_measured_debt(db_session: AsyncSession) -> None:
    """Yirmiyahu 44 against a scheduled 47: three perakim owed, straight out of the file."""
    await _seed(db_session)
    track = await _track(db_session, "Neviim")
    assert track.anchor_ordinal - await actual_ordinal(db_session, track) == 3


async def test_a_track_without_a_scheduled_ref_starts_square(db_session: AsyncSession) -> None:
    await _seed(db_session)
    track = await _track(db_session, "David Hadar — Brachot")
    assert track.anchor_ordinal == await actual_ordinal(db_session, track)


async def test_an_unopened_track_has_no_advance_and_stands_at_zero(db_session: AsyncSession) -> None:
    await _seed(db_session)
    track = await _track(db_session, "Likutei Sichot")
    assert await actual_ordinal(db_session, track) == 0
    assert track.anchor_ordinal == 1
    assert track.starts_on == date(2026, 10, 10)


async def test_a_chumash_position_resolves_through_the_aliyot(db_session: AsyncSession) -> None:
    """Parsha2 Shlishi is the tenth aliyah of the cycle, not the eleventh row."""
    await _seed(db_session)
    track = await _track(db_session, "Chumash")
    assert await actual_ordinal(db_session, track) == 10


async def test_every_advance_carries_the_hebrew_date_of_the_day_it_happened(db_session: AsyncSession) -> None:
    await _seed(db_session)
    dates = (await db_session.execute(select(Advance.hebrew_date))).scalars().all()
    assert set(dates) == {HEBREW_AS_OF}


async def test_the_parsha_tag_lands_on_both_categories(db_session: AsyncSession) -> None:
    await _seed(db_session)
    rows = (
        await db_session.execute(
            select(Track.name_en, Track.category).join(track_tag, track_tag.c.track_id == Track.id)
        )
    ).all()
    assert {name for name, _ in rows} == {"Chumash", "Likutei Sichot"}
    assert len({category for _, category in rows}) == 2


async def test_a_chavrusa_track_is_linked_to_its_chavrusa(db_session: AsyncSession) -> None:
    await _seed(db_session)
    track = await _track(db_session, "David Hadar — Brachot")
    chavrusa = (await db_session.execute(select(Chavrusa).where(Chavrusa.id == track.chavrusa_id))).scalar_one()
    assert chavrusa.name == "David Hadar"


async def test_seeding_twice_yields_the_same_rows(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await seed_tracks(db_session, parse_tracks_file(TRACKS_YAML))
    assert await db_session.scalar(select(func.count()).select_from(Track)) == 4
    assert await db_session.scalar(select(func.count()).select_from(Advance)) == 3
    assert await db_session.scalar(select(func.count()).select_from(track_tag)) == 2


async def test_a_position_that_does_not_resolve_stops_the_seed(db_session: AsyncSession) -> None:
    """A typo must fail loudly rather than place a track in the wrong masechta."""
    await _catalog(db_session)
    await _calendar(db_session)
    broken = TRACKS_YAML.replace("current_ref: Jeremiah 44", "current_ref: Jeremiah 99")
    with pytest.raises(ValueError, match="Jeremiah 99"):
        await seed_tracks(db_session, parse_tracks_file(broken))


async def test_a_missing_calendar_day_stops_the_seed(db_session: AsyncSession) -> None:
    """An advance without a real Hebrew date would misdate the app's first twenty rows."""
    await _catalog(db_session)
    with pytest.raises(ValueError, match="2026-08-24"):
        await seed_tracks(db_session, parse_tracks_file(TRACKS_YAML))


async def test_clearing_the_ledger_leaves_the_catalog(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await clear_ledger(db_session)
    assert await ledger_is_empty(db_session)
    assert await db_session.scalar(select(func.count()).select_from(Work)) > 0


async def test_an_empty_ledger_reports_itself(db_session: AsyncSession) -> None:
    assert await ledger_is_empty(db_session)
    await _seed(db_session)
    assert not await ledger_is_empty(db_session)


async def test_a_sidra_with_no_tags_seeds_cleanly(db_session: AsyncSession) -> None:
    """Tags are optional; a file that declares none must not trip the association insert."""
    await _catalog(db_session)
    await _calendar(db_session)
    untagged = TRACKS_YAML.replace("    tags: [parsha]\n", "").replace(
        'tags:\n  - name: parsha\n    name_he: פרשה\n    color: "#8a6d3b"\n', "tags: []\n"
    )
    counts = await seed_tracks(db_session, parse_tracks_file(untagged))
    assert (counts.tags, counts.tagged) == (0, 0)
    assert await db_session.scalar(select(func.count()).select_from(track_tag)) == 0


UNOPENED_YAML = """
as_of: 2026-08-24
tags: []
chavrusas: []
tracks:
  - name_en: Shulchan Aruch
    name_he: שולחן ערוך
    category: daily
    kind: corpus
    corpus_id: neviim
    rate: 1
    period: day
"""


async def test_a_track_with_no_position_at_all_anchors_at_one(db_session: AsyncSession) -> None:
    """Shulchan Aruch's shape: never opened, no scheduled position, no start date declared."""
    await _catalog(db_session)
    await _calendar(db_session)
    await seed_tracks(db_session, parse_tracks_file(UNOPENED_YAML))

    track = await _track(db_session, "Shulchan Aruch")
    assert track.anchor_ordinal == 1
    assert track.anchor_date == AS_OF
    assert track.starts_on is None
    assert await actual_ordinal(db_session, track) == 0
