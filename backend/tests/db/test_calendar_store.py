from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.calendar.calendar_day import CalendarDay
from sidra.calendar.store import calendar_day, calendar_span, store_calendar
from sidra.db.models import CalendarDayRow

pytestmark = pytest.mark.integration


def _day(day: int, parsha: tuple[str, ...] = ("Ki Tavo",), yom_tov: bool = False) -> CalendarDay:
    return CalendarDay(
        civil_date=date(2026, 8, day),
        hebrew_date="י״ב בֶּאֱלוּל תשפ״ו",
        parsha_en=parsha,
        parsha_he=("כי תבוא",) * len(parsha),
        is_yom_tov=yom_tov,
    )


async def test_a_range_stores_and_reads_back(db_session: AsyncSession) -> None:
    assert await store_calendar(db_session, [_day(24), _day(25)]) == 2
    found = await calendar_day(db_session, date(2026, 8, 24))
    assert found.parsha_en == ("Ki Tavo",)
    assert found.hebrew_date == "י״ב בֶּאֱלוּל תשפ״ו"


async def test_a_combined_week_round_trips(db_session: AsyncSession) -> None:
    await store_calendar(db_session, [_day(24, ("Nitzavim", "Vayeilech"))])
    found = await calendar_day(db_session, date(2026, 8, 24))
    assert found.parsha_en == ("Nitzavim", "Vayeilech")
    assert found.is_combined_parsha
    assert found.aliyot_this_week == 14


async def test_storing_twice_is_idempotent(db_session: AsyncSession) -> None:
    await store_calendar(db_session, [_day(24), _day(25)])
    await store_calendar(db_session, [_day(24), _day(25)])
    assert await db_session.scalar(select(func.count()).select_from(CalendarDayRow)) == 2


async def test_a_missing_day_raises_naming_the_date(db_session: AsyncSession) -> None:
    """Assuming no parsha would put the Chumash track quietly out of step."""
    await store_calendar(db_session, [_day(24)])
    with pytest.raises(ValueError, match="2026-08-25"):
        await calendar_day(db_session, date(2026, 8, 25))


async def test_an_empty_range_raises(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="no calendar days"):
        await store_calendar(db_session, [])


async def test_yom_tov_survives_the_round_trip(db_session: AsyncSession) -> None:
    await store_calendar(db_session, [_day(24, yom_tov=True)])
    assert (await calendar_day(db_session, date(2026, 8, 24))).is_yom_tov is True


async def test_a_contiguous_span_reads_back_in_order(db_session: AsyncSession) -> None:
    await store_calendar(db_session, [_day(24), _day(25), _day(26)])
    span = await calendar_span(db_session, date(2026, 8, 24), date(2026, 8, 26))
    assert [day.civil_date.day for day in span] == [24, 25, 26]


async def test_a_single_day_span_reads_back(db_session: AsyncSession) -> None:
    await store_calendar(db_session, [_day(24)])
    assert len(await calendar_span(db_session, date(2026, 8, 24), date(2026, 8, 24))) == 1


async def test_a_hole_in_the_middle_raises_naming_the_first_missing_day(db_session: AsyncSession) -> None:
    """A silent gap would under-accrue, so the Chumash would look square while three aliyot behind."""
    await store_calendar(db_session, [_day(24)])
    await store_calendar(db_session, [_day(26)])
    with pytest.raises(ValueError, match="no calendar snapshot for 2026-08-25"):
        await calendar_span(db_session, date(2026, 8, 24), date(2026, 8, 26))


async def test_a_span_running_past_the_snapshot_raises_at_the_first_day_beyond_it(
    db_session: AsyncSession,
) -> None:
    await store_calendar(db_session, [_day(24), _day(25)])
    with pytest.raises(ValueError, match="no calendar snapshot for 2026-08-26"):
        await calendar_span(db_session, date(2026, 8, 24), date(2026, 8, 27))


async def test_a_span_starting_before_the_snapshot_raises_at_its_first_day(db_session: AsyncSession) -> None:
    await store_calendar(db_session, [_day(25)])
    with pytest.raises(ValueError, match="no calendar snapshot for 2026-08-24"):
        await calendar_span(db_session, date(2026, 8, 24), date(2026, 8, 25))


async def test_an_inverted_span_raises(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="precedes start"):
        await calendar_span(db_session, date(2026, 8, 26), date(2026, 8, 24))
