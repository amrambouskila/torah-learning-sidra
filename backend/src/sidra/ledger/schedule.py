"""The debt ledger.

A track holds a rate, a period and an anchor. Everything else is arithmetic:

    scheduled = anchor_ordinal + rate x periods_elapsed(effective anchor -> today)
    debt      = scheduled - actual        negative debt is credit, and it banks

Nothing here is stored. It is recomputed per request, so derived state cannot drift from the
ledger, and a rule change touches one module rather than a migration.

The clock ticks **every calendar day**, Shabbos and Yom Tov included. Debt is debt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sidra.ledger.effective_anchor import effective_anchor
from sidra.ledger.period import Period

DAYS_PER_WEEK = 7


@dataclass(frozen=True, slots=True)
class LedgerState:
    """What a track owes, or has banked, on a given day."""

    scheduled: int
    actual: int
    debt: int
    """Positive means behind. Negative means ahead, and the surplus carries forward."""

    days_ahead: int
    """The display form of a credit. Never negative, so it cannot read as licence to stop."""

    starts_in_days: int | None
    """Set when the track has not begun. Such a track accrues no debt."""

    @classmethod
    def not_started(
        cls,
        *,
        anchor_ordinal: int,
        actual_ordinal: int,
        starts_on: date,
        today: date,
    ) -> LedgerState:
        """A track whose start date is still ahead: no debt, and a countdown.

        Built before any origin arithmetic runs, and that ordering is load-bearing twice over: a
        future origin makes ``periods_elapsed`` raise, and a span that has not begun demands
        calendar days nobody has stored. Either surfaces as a 409 across a whole screen.
        """
        return cls(
            scheduled=anchor_ordinal,
            actual=actual_ordinal,
            debt=0,
            days_ahead=0,
            starts_in_days=(starts_on - today).days,
        )

    @property
    def is_behind(self) -> bool:
        return self.debt > 0

    @property
    def has_started(self) -> bool:
        return self.starts_in_days is None


def periods_elapsed(anchor: date, today: date, period: Period) -> int:
    """How many periods have passed, counting the anchor day itself as the first.

    A chavrusa track has no period: it moves when they meet, so asking how many have elapsed is a
    category error rather than a zero.
    """
    if period is Period.NONE:
        raise ValueError("a track with period 'none' has no schedule; it carries staleness, not debt")
    if today < anchor:
        raise ValueError(f"today ({today}) precedes the anchor ({anchor})")

    days = (today - anchor).days + 1
    return days if period is Period.DAY else (days + DAYS_PER_WEEK - 1) // DAYS_PER_WEEK


def scheduled_ordinal(anchor_ordinal: int, rate: int, periods: int, *, total: int | None = None) -> int:
    """Where the schedule says the track should be.

    Clamped to ``total`` when given: a finished work is finished, and a schedule that ran past its
    end would report a debt no amount of learning could clear.
    """
    if rate < 1:
        raise ValueError(f"rate must be at least 1, got {rate}")
    scheduled = anchor_ordinal + rate * (periods - 1)
    return min(scheduled, total) if total is not None else scheduled


def ledger_state(
    *,
    anchor_date: date,
    anchor_ordinal: int,
    rate: int,
    period: Period,
    actual_ordinal: int,
    today: date,
    starts_on: date | None = None,
    total: int | None = None,
) -> LedgerState:
    """Compute what a track owes today.

    A track whose ``starts_on`` is still ahead accrues nothing: it reports zero debt and a
    countdown, which is what the three parsha-weekly works do until Shabbos Bereishis. Once that
    day arrives the schedule counts from it, not from the anchor -- otherwise the track would open
    as far behind as the wait had been long.
    """
    if starts_on is not None and today < starts_on:
        return LedgerState.not_started(
            anchor_ordinal=anchor_ordinal, actual_ordinal=actual_ordinal, starts_on=starts_on, today=today
        )

    origin = effective_anchor(anchor_date, starts_on)
    scheduled = scheduled_ordinal(anchor_ordinal, rate, periods_elapsed(origin, today, period), total=total)
    debt = scheduled - actual_ordinal
    return LedgerState(
        scheduled=scheduled,
        actual=actual_ordinal,
        debt=debt,
        days_ahead=max(0, -debt) // rate,
        starts_in_days=None,
    )
