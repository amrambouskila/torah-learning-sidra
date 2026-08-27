from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.calendar.calendar_day import CalendarDay
from sidra.db.models.calendar_day import CalendarDayRow


async def store_calendar(session: AsyncSession, days: Sequence[CalendarDay]) -> int:
    """Replace the snapshotted range. Idempotent: storing the same range twice is a no-op."""
    if not days:
        raise ValueError("no calendar days supplied")
    start, end = days[0].civil_date, days[-1].civil_date
    await session.execute(
        delete(CalendarDayRow).where(CalendarDayRow.civil_date >= start, CalendarDayRow.civil_date <= end)
    )
    session.add_all(
        [
            CalendarDayRow(
                civil_date=day.civil_date,
                hebrew_date=day.hebrew_date,
                parsha_en=list(day.parsha_en),
                parsha_he=list(day.parsha_he),
                is_yom_tov=day.is_yom_tov,
            )
            for day in days
        ]
    )
    await session.flush()
    return len(days)


async def calendar_day(session: AsyncSession, on: date) -> CalendarDay:
    """Read one snapshotted day.

    A missing day raises naming the date rather than returning a default: silently assuming no
    parsha would put the Chumash track quietly out of step.
    """
    row = (await session.execute(select(CalendarDayRow).where(CalendarDayRow.civil_date == on))).scalar_one_or_none()
    if row is None:
        raise ValueError(f"no calendar snapshot for {on}; run 'sidra-db calendar' to extend the range")
    return CalendarDay(
        civil_date=row.civil_date,
        hebrew_date=row.hebrew_date,
        parsha_en=tuple(row.parsha_en),
        parsha_he=tuple(row.parsha_he),
        is_yom_tov=row.is_yom_tov,
    )


async def calendar_span(session: AsyncSession, start: date, end: date) -> list[CalendarDay]:
    """Read a contiguous span. Raises if any day in it is missing, naming the first gap.

    The parsha schedules accrue day by day, so a hole in the snapshot would silently under-accrue
    rather than fail -- and a track that looks square while being three aliyot behind is worse than
    one that refuses to render.
    """
    if end < start:
        raise ValueError(f"end ({end}) precedes start ({start})")
    rows = (
        (
            await session.execute(
                select(CalendarDayRow)
                .where(CalendarDayRow.civil_date >= start, CalendarDayRow.civil_date <= end)
                .order_by(CalendarDayRow.civil_date)
            )
        )
        .scalars()
        .all()
    )

    expected = start
    for row in rows:
        if row.civil_date != expected:
            raise ValueError(f"no calendar snapshot for {expected}; run 'sidra-db calendar' to extend the range")
        expected += timedelta(days=1)
    if expected != end + timedelta(days=1):
        raise ValueError(f"no calendar snapshot for {expected}; run 'sidra-db calendar' to extend the range")

    return [
        CalendarDay(
            civil_date=row.civil_date,
            hebrew_date=row.hebrew_date,
            parsha_en=tuple(row.parsha_en),
            parsha_he=tuple(row.parsha_he),
            is_yom_tov=row.is_yom_tov,
        )
        for row in rows
    ]
