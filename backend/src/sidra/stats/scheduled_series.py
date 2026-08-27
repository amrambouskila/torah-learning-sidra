"""What a track's schedule had billed by the end of each day in a span.

Debt over time is not stored -- only advances are -- but it is exactly reconstructable, because
both sides of ``debt = scheduled - actual`` are closed forms of the day. This is the ``scheduled``
side. The reconstruction is as of *now*: rebasing a start date moves every past value, which is
the same property ``/api/today`` already has, extended backwards.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sidra.calendar.calendar_day import CalendarDay
from sidra.db.models import Track
from sidra.ledger.parsha_schedule import aliyot_accrued, parshiyos_accrued
from sidra.ledger.schedule import periods_elapsed, scheduled_ordinal
from sidra.ledger.track_kind import TrackKind


def fixed_rate_series(track: Track, origin: date, days: Sequence[date]) -> list[int]:
    """A flat-rate track: one closed form per day, no database and no calendar."""
    return [
        scheduled_ordinal(track.anchor_ordinal, track.rate, periods_elapsed(origin, day, track.period))
        if day >= origin
        else track.anchor_ordinal
        for day in days
    ]


def parsha_series(track: Track, origin: date, days: Sequence[date], span: Sequence[CalendarDay]) -> list[int]:
    """A calendar-driven track.

    ``span`` must run from ``origin`` through the last day asked for, not from the window's start:
    the accrual is path-dependent -- a combined week is counted by runs -- so handing it a span
    that begins mid-history under-accrues silently.
    """
    accrue = aliyot_accrued if track.kind is TrackKind.PARSHA_ALIYAH else parshiyos_accrued
    by_day = {day.civil_date: index for index, day in enumerate(span)}
    series = []
    for day in days:
        if day < origin or day not in by_day:
            series.append(track.anchor_ordinal)
            continue
        series.append(track.anchor_ordinal + accrue(span[: by_day[day] + 1]) - 1)
    return series
