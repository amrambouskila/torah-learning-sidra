"""Seed the real sidra against the real catalog and check the measured debts.

The two numbers this asserts were measured off Amram's Obsidian note on 2026-08-24 and are the
acceptance criteria for P2: Avoda Zara 28b against a scheduled 38b is twenty amudim, Yirmiyahu 44
against a scheduled 47 is three perakim.

Run deliberately:  uv run pytest -m live -k sidra
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.calendar.calendar_source import fetch_calendar_range
from sidra.calendar.load_parsha_index import load_parsha_index
from sidra.calendar.store import store_calendar
from sidra.catalog.crawl import crawl_catalog
from sidra.catalog.sefaria_client import SefariaClient
from sidra.constants import SEFARIA_BASE_URL
from sidra.db.models import Track
from sidra.ledger.category import Category
from sidra.ledger.position import position_at, track_total
from sidra.ledger.schedule import ledger_state
from sidra.ledger.seed_tracks import actual_ordinal, seed_tracks
from sidra.ledger.track_kind import TrackKind
from sidra.ledger.tracks_file import load_tracks_file

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
async def sidra(db_engine: object) -> AsyncIterator[AsyncSession]:
    """Crawl Sefaria, seed the catalog, fetch the calendar and seed the real tracks. Once."""
    from sidra.db.engine import create_session_factory
    from sidra.db.seed import clear_catalog, seed_from_snapshot
    from sidra.ledger.seed_tracks import clear_ledger

    spec_file = load_tracks_file()
    async with httpx.AsyncClient(timeout=180.0) as async_http:
        client = SefariaClient(async_http, SEFARIA_BASE_URL)
        with httpx.Client(timeout=300.0) as sync_http:
            result = await crawl_catalog(client, sync_http, include_links=False)
    factory = create_session_factory(db_engine)  # type: ignore[arg-type]
    async with factory() as session:
        await seed_from_snapshot(session, result.payload)
        # The calendar is resolved against the catalog's parshiyos, so it is read after the
        # snapshot lands rather than alongside the crawl.
        index = await load_parsha_index(session)
        async with httpx.AsyncClient(timeout=180.0) as calendar_http:
            days = await fetch_calendar_range(calendar_http, spec_file.as_of, spec_file.as_of, index)
        await store_calendar(session, days)
        await seed_tracks(session, spec_file)
        await session.commit()
        yield session
        await clear_ledger(session)
        await clear_catalog(session)
        await session.commit()


async def _track(session: AsyncSession, name: str) -> Track:
    return (await session.execute(select(Track).where(Track.name_en == name))).scalar_one()


async def _debt(session: AsyncSession, name: str) -> int:
    track = await _track(session, name)
    state = ledger_state(
        anchor_date=track.anchor_date,
        anchor_ordinal=track.anchor_ordinal,
        rate=track.rate,
        period=track.period,
        actual_ordinal=await actual_ordinal(session, track),
        today=track.anchor_date,
        starts_on=track.starts_on,
        total=await track_total(session, track),
    )
    return state.debt


async def test_the_gemara_track_owes_twenty_amudim(sidra: AsyncSession) -> None:
    assert await _debt(sidra, "Gemara") == 20


async def test_the_neviim_track_owes_three_perakim(sidra: AsyncSession) -> None:
    assert await _debt(sidra, "Neviim") == 3


async def test_the_two_debts_resolve_to_the_refs_amram_wrote(sidra: AsyncSession) -> None:
    gemara = await _track(sidra, "Gemara")
    neviim = await _track(sidra, "Neviim")
    assert (await position_at(sidra, gemara, await actual_ordinal(sidra, gemara))).ref == "Avodah Zarah 28b"
    assert (await position_at(sidra, gemara, gemara.anchor_ordinal)).ref == "Avodah Zarah 38b"
    assert (await position_at(sidra, neviim, await actual_ordinal(sidra, neviim))).ref == "Jeremiah 44"
    assert (await position_at(sidra, neviim, neviim.anchor_ordinal)).ref == "Jeremiah 47"


async def test_every_seeded_position_resolves_to_a_real_unit(sidra: AsyncSession) -> None:
    """The whole point of resolving refs at seed time: no track can be pointing at nothing."""
    tracks = (await sidra.execute(select(Track))).scalars().all()
    for track in tracks:
        ordinal = await actual_ordinal(sidra, track)
        if ordinal:
            assert (await position_at(sidra, track, ordinal)).ref


async def test_the_corpus_sizes_match_the_spec(sidra: AsyncSession) -> None:
    """Sizes from spec section 6, each independently derived from the shape arrays.

    Shulchan Aruch is the 1,705 simanim of the four chalakim. Even HaEzer's two one-node
    appendices -- Seder HaGet and Seder Halitzah, the procedural orders for writing a get and for
    chalitzah -- are excluded: they are not simanim anybody learns one a day.
    """
    expected = {
        "Neviim": 380,
        "Ketuvim": 362,
        "Mishna": 525,
        "Shulchan Aruch": 1_705,
        "Chumash": 378,
        "Gemara": 150,
    }
    for name, size in expected.items():
        assert await track_total(sidra, await _track(sidra, name)) == size, name


async def test_the_shulchan_aruch_begins_at_orach_chaim(sidra: AsyncSession) -> None:
    """Sefaria returns the chalakim alphabetically, which would open the cycle at Choshen Mishpat."""
    track = await _track(sidra, "Shulchan Aruch")
    assert (await position_at(sidra, track, 1)).ref == "Shulchan Arukh, Orach Chayim 1"
    assert (await position_at(sidra, track, 698)).ref == "Shulchan Arukh, Yoreh De'ah 1"
    # The last siman is the track's last unit: 697 + 403 + 178 + 427. It read 1,707 while Sefaria
    # still served Even HaEzer's two appendices as works, which padded the position space past the
    # 1,705 the totals test four lines up has always asserted.
    assert (await position_at(sidra, track, 1_705)).ref == "Shulchan Arukh, Choshen Mishpat 427"


async def test_the_two_rambam_chavrusas_run_the_rambams_own_order(sidra: AsyncSession) -> None:
    """Deos is Sefer Madda's second book and Avoda Zara its fourth; the tracks are independent."""
    jacob = await _track(sidra, "Rabbi Jacob — Mishneh Torah")
    cohen = await _track(sidra, "David Cohen — Mishneh Torah")
    jacob_at = await position_at(sidra, jacob, await actual_ordinal(sidra, jacob))
    cohen_at = await position_at(sidra, cohen, await actual_ordinal(sidra, cohen))
    assert jacob_at.ref == "Mishneh Torah, Foreign Worship and Customs of the Nations 5:2"
    assert cohen_at.ref == "Mishneh Torah, Human Dispositions 5:8"
    assert jacob_at.corpus_ordinal > cohen_at.corpus_ordinal


async def test_the_three_parsha_weekly_tracks_have_not_started(sidra: AsyncSession) -> None:
    weekly = [t for t in (await sidra.execute(select(Track))).scalars().all() if t.kind is TrackKind.PARSHA_WEEKLY]
    assert len(weekly) == 3
    for track in weekly:
        assert await actual_ordinal(sidra, track) == 0
        assert await track_total(sidra, track) == 54


async def test_the_sidra_is_twenty_tracks_across_three_categories(sidra: AsyncSession) -> None:
    tracks = (await sidra.execute(select(Track))).scalars().all()
    assert len(tracks) == 20
    counts = {category: sum(1 for t in tracks if t.category is category) for category in Category}
    assert counts == {Category.DAILY: 6, Category.SHABBAT: 9, Category.CHAVRUSA: 5}
