"""The two calendar-driven schedules.

Every other track has a fixed rate: one amud a day, one siman a day. The Chumash and the three
parsha-weekly works do not, because the calendar sets their pace. A combined week -- Vayakhel-
Pekudei, Nitzavim-Vayeilech -- supplies two parshiyos, so it supplies fourteen aliyot rather than
seven, and the daily load doubles rather than the text being halved. That is also the only way
fifty-four parshiyos fit into roughly fifty weeks.

Both schedules are debt ledgers like any other: a missed aliyah is owed, not forgiven, and the
track stays in the unfinished parsha while the schedule moves on.

These are pure functions over a span of ``CalendarDay``. The caller reads the span out of the
snapshot; nothing here touches the network.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from sidra.calendar.calendar_day import CalendarDay
from sidra.ledger.schedule import LedgerState


def _checked(days: Sequence[CalendarDay]) -> Sequence[CalendarDay]:
    """A span must be non-empty and one day at a time; a gap would silently mis-accrue."""
    if not days:
        raise ValueError("no calendar days in the span")
    for earlier, later in zip(days, days[1:], strict=False):
        if later.civil_date != earlier.civil_date + timedelta(days=1):
            raise ValueError(f"calendar span is not contiguous: {earlier.civil_date} then {later.civil_date}")
    return days


def aliyot_accrued(days: Sequence[CalendarDay]) -> int:
    """How many aliyot the schedule has handed out across the span -- one per parsha per day.

    A day the calendar names no parsha for accrues nothing. Under-accruing is the safe direction:
    a gap in the source can leave the track looking ahead, but it can never invent a debt.
    """
    return sum(day.parsha_count for day in _checked(days))


def parshiyos_accrued(days: Sequence[CalendarDay]) -> int:
    """How many parshiyos the span covers, counting each week once.

    Counted by runs rather than by distinct names, so the second year of a cycle counts again and
    a day the calendar skips does not split one week into two.
    """
    total = 0
    running: tuple[str, ...] = ()
    for day in _checked(days):
        if not day.parsha_count:
            continue
        if day.parsha_en != running:
            total += day.parsha_count
            running = day.parsha_en
    return total


def _state(
    *,
    anchor_ordinal: int,
    actual_ordinal: int,
    accrued: int,
    rate_today: int,
    total: int | None,
) -> LedgerState:
    scheduled = anchor_ordinal + accrued - 1
    if total is not None:
        scheduled = min(scheduled, total)
    debt = scheduled - actual_ordinal
    return LedgerState(
        scheduled=scheduled,
        actual=actual_ordinal,
        debt=debt,
        days_ahead=max(0, -debt) // max(1, rate_today),
        starts_in_days=None,
    )


def parsha_aliyah_state(
    *,
    anchor_ordinal: int,
    actual_ordinal: int,
    days: Sequence[CalendarDay],
    total: int | None = None,
) -> LedgerState:
    """What the Chumash track owes, one aliyah a day and two in a combined week.

    ``days`` runs from the track's effective anchor through today, inclusive -- its start date
    when it has one, its anchor date otherwise. The first day of the span is a learning day.
    """
    span = _checked(days)
    return _state(
        anchor_ordinal=anchor_ordinal,
        actual_ordinal=actual_ordinal,
        accrued=aliyot_accrued(span),
        rate_today=span[-1].parsha_count,
        total=total,
    )


def parsha_weekly_state(
    *,
    anchor_ordinal: int,
    actual_ordinal: int,
    days: Sequence[CalendarDay],
    total: int | None = None,
) -> LedgerState:
    """What a parsha-weekly work owes -- one unit per parsha, so two in a combined week.

    ``days`` runs from the track's effective anchor through today, inclusive.
    """
    span = _checked(days)
    return _state(
        anchor_ordinal=anchor_ordinal,
        actual_ordinal=actual_ordinal,
        accrued=parshiyos_accrued(span),
        rate_today=1,
        total=total,
    )
