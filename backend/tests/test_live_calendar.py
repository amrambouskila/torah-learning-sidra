"""Verify the Hebrew calendar against the real APIs.

Run deliberately:  uv run pytest -m live -k calendar
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

import httpx
import pytest

from sidra.calendar.calendar_source import fetch_calendar_range
from sidra.calendar.parsha_index import ParshaIndex
from sidra.catalog.granularity import Granularity
from sidra.catalog.ingest_parsha import ingest_parshiyos
from sidra.catalog.sefaria_client import SefariaClient
from sidra.constants import SEFARIA_BASE_URL

pytestmark = pytest.mark.live


@pytest.fixture(scope="session")
async def index() -> AsyncIterator[ParshaIndex]:
    """The real fifty-four, from the same ingest the catalog is built by."""
    async with httpx.AsyncClient(timeout=120.0) as http:
        _, rows = await ingest_parshiyos(SefariaClient(http, SEFARIA_BASE_URL))
    yield ParshaIndex.from_names((row.label_en, row.label_he) for row in rows if row.granularity is Granularity.PARSHA)


async def test_shabbos_bereishis_2026_falls_on_the_tenth_of_october(index: ParshaIndex) -> None:
    """The date the three parsha-weekly tracks begin."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        days = await fetch_calendar_range(client, date(2026, 10, 6), date(2026, 10, 10), index)
    assert all("Bereshit" in "".join(day.parsha_en) for day in days), [d.parsha_en for d in days]


async def test_a_real_combined_week_is_detected(index: ParshaIndex) -> None:
    """Nitzavim-Vayeilech, the week of 1 September 2026."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        days = await fetch_calendar_range(client, date(2026, 9, 1), date(2026, 9, 1), index)
    day = days[0]
    assert day.is_combined_parsha, day.parsha_en
    assert day.parsha_en == ("Nitzavim", "Vayeilech")
    assert day.aliyot_this_week == 14


async def test_yom_tov_and_hebrew_dates_come_through(index: ParshaIndex) -> None:
    async with httpx.AsyncClient(timeout=120.0) as client:
        days = await fetch_calendar_range(client, date(2026, 10, 2), date(2026, 10, 5), index)
    assert any(day.is_yom_tov for day in days)
    assert all(day.hebrew_date for day in days)
    assert all(any("֐" <= c <= "׿" for c in day.hebrew_date) for day in days)


async def test_a_hyphenated_name_and_a_festival_week_are_read_correctly(index: ParshaIndex) -> None:
    """The two live bugs, against the real API: Lech-Lecha is one parsha, and Rosh Hashana week
    supplies none. Both used to bill a week that was never read."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        lech = await fetch_calendar_range(client, date(2026, 10, 20), date(2026, 10, 20), index)
        rosh = await fetch_calendar_range(client, date(2026, 9, 10), date(2026, 9, 10), index)
    assert lech[0].parsha_count == 1, lech[0].parsha_en
    assert rosh[0].parsha_count == 0, rosh[0].parsha_en


async def test_one_whole_cycle_bills_every_parsha_exactly_once(index: ParshaIndex) -> None:
    """The fact the annual wrap rests on, measured rather than reasoned.

    Slow on purpose -- it crawls a real year, throttled, because the only honest way to know what
    a cycle bills is to bill one. Sefaria never names V'Zot HaBerachah (it is read on Simchat
    Torah, never a Shabbos in the diaspora), so before ``close_the_cycle`` a cycle billed 53
    parshiyos and 371 aliyot, and any modulo over 378 would have slipped a whole parsha a year,
    cumulatively and forever.
    """
    async with httpx.AsyncClient(timeout=300.0) as client:
        days = await fetch_calendar_range(client, date(2026, 10, 4), date(2027, 10, 23), index, pause_seconds=0.4)

    billed = [name for day in days for name in day.parsha_en]
    assert len(billed) == 378, len(billed)
    assert len(set(billed)) == 54, sorted(set(billed))
