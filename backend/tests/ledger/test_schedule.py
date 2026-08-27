from __future__ import annotations

from datetime import date

import pytest

from sidra.catalog.bavli_amudim import real_amudim
from sidra.ledger.period import Period
from sidra.ledger.schedule import LedgerState, ledger_state, periods_elapsed, scheduled_ordinal

ANCHOR = date(2026, 8, 24)
AVODAH_ZARAH = [0 if index in {0, 1} else 7 for index in range(152)]


def _seq(label: str) -> int:
    """1-based position among real amudim. Never the shape index."""
    return real_amudim(AVODAH_ZARAH).index(label) + 1


# --------------------------------------------------------------------------- periods_elapsed


@pytest.mark.parametrize(
    ("today", "expected"),
    [(ANCHOR, 1), (date(2026, 8, 25), 2), (date(2026, 8, 31), 8), (date(2026, 9, 23), 31)],
)
def test_daily_periods_count_the_anchor_day_itself(today: date, expected: int) -> None:
    assert periods_elapsed(ANCHOR, today, Period.DAY) == expected


@pytest.mark.parametrize(
    ("today", "expected"),
    [(ANCHOR, 1), (date(2026, 8, 30), 1), (date(2026, 8, 31), 2), (date(2026, 9, 6), 2), (date(2026, 9, 7), 3)],
)
def test_weekly_periods_round_up(today: date, expected: int) -> None:
    assert periods_elapsed(ANCHOR, today, Period.WEEK) == expected


def test_a_date_before_the_anchor_raises() -> None:
    with pytest.raises(ValueError, match="precedes the anchor"):
        periods_elapsed(ANCHOR, date(2026, 8, 23), Period.DAY)


def test_a_chavrusa_track_has_no_schedule() -> None:
    """Asking how many periods have elapsed for a chavrusa is a category error, not a zero."""
    with pytest.raises(ValueError, match="staleness, not debt"):
        periods_elapsed(ANCHOR, ANCHOR, Period.NONE)


# --------------------------------------------------------------------------- scheduled_ordinal


def test_the_schedule_advances_by_the_rate() -> None:
    assert scheduled_ordinal(10, 1, 1) == 10
    assert scheduled_ordinal(10, 1, 5) == 14
    assert scheduled_ordinal(10, 2, 5) == 18


def test_the_schedule_is_clamped_to_the_total() -> None:
    """A finished work is finished; a schedule past its end would report unclearable debt."""
    assert scheduled_ordinal(1, 1, 500, total=150) == 150


def test_a_rate_below_one_raises() -> None:
    with pytest.raises(ValueError, match="rate must be at least 1"):
        scheduled_ordinal(1, 0, 5)


# --------------------------------------------------------------------------- the measured debts


def test_the_gemara_debt_is_twenty_amudim() -> None:
    """The real position: actual Avoda Zara 28b, scheduled 38b. Both seqs derived, not hard-coded."""
    actual, scheduled = _seq("28b"), _seq("38b")
    state = ledger_state(
        anchor_date=ANCHOR,
        anchor_ordinal=scheduled,
        rate=1,
        period=Period.DAY,
        actual_ordinal=actual,
        today=ANCHOR,
        total=150,
    )
    assert state.debt == 20
    assert state.is_behind
    assert state.days_ahead == 0


def test_the_neviim_debt_is_three_perakim() -> None:
    """The real position: actual Yirmiyahu 44, scheduled 47."""
    state = ledger_state(
        anchor_date=ANCHOR,
        anchor_ordinal=47,
        rate=1,
        period=Period.DAY,
        actual_ordinal=44,
        today=ANCHOR,
        total=52,
    )
    assert state.debt == 3


def test_the_debt_grows_by_one_a_day_when_nothing_is_learned() -> None:
    """This is what makes a projected finish date slide by exactly one day per day behind."""
    common = {
        "anchor_date": ANCHOR,
        "anchor_ordinal": 74,
        "rate": 1,
        "period": Period.DAY,
        "actual_ordinal": 54,
        "total": 150,
    }
    assert ledger_state(**common, today=ANCHOR).debt == 20  # type: ignore[arg-type]
    assert ledger_state(**common, today=date(2026, 8, 25)).debt == 21  # type: ignore[arg-type]
    assert ledger_state(**common, today=date(2026, 8, 31)).debt == 27  # type: ignore[arg-type]


# --------------------------------------------------------------------------- banking


def test_a_track_exactly_on_schedule_owes_nothing() -> None:
    state = ledger_state(
        anchor_date=ANCHOR, anchor_ordinal=10, rate=1, period=Period.DAY, actual_ordinal=10, today=ANCHOR
    )
    assert state.debt == 0
    assert state.days_ahead == 0
    assert not state.is_behind


def test_surplus_banks_and_shows_as_days_ahead() -> None:
    """Three extra units on a one-a-day track is three days ahead, not a negative number."""
    state = ledger_state(
        anchor_date=ANCHOR, anchor_ordinal=10, rate=1, period=Period.DAY, actual_ordinal=13, today=ANCHOR
    )
    assert state.debt == -3
    assert state.days_ahead == 3
    assert not state.is_behind


def test_banked_credit_absorbs_missed_days() -> None:
    """Learning three ahead then missing three days returns the track to level."""
    common = {"anchor_date": ANCHOR, "anchor_ordinal": 10, "rate": 1, "period": Period.DAY, "actual_ordinal": 13}
    assert ledger_state(**common, today=ANCHOR).days_ahead == 3  # type: ignore[arg-type]
    assert ledger_state(**common, today=date(2026, 8, 26)).days_ahead == 1  # type: ignore[arg-type]
    assert ledger_state(**common, today=date(2026, 8, 27)).debt == 0  # type: ignore[arg-type]
    assert ledger_state(**common, today=date(2026, 8, 28)).debt == 1  # type: ignore[arg-type]


def test_days_ahead_accounts_for_the_rate() -> None:
    """Four units ahead on a two-a-day track is two days, not four."""
    state = ledger_state(
        anchor_date=ANCHOR, anchor_ordinal=10, rate=2, period=Period.DAY, actual_ordinal=14, today=ANCHOR
    )
    assert state.debt == -4
    assert state.days_ahead == 2


# --------------------------------------------------------------------------- the clock and start dates


def test_the_clock_ticks_on_shabbos_and_yom_tov() -> None:
    """No exceptions: an unlearned Shabbos accrues a unit like any other day."""
    saturday = date(2026, 8, 29)
    assert periods_elapsed(ANCHOR, saturday, Period.DAY) == 6
    state = ledger_state(
        anchor_date=ANCHOR, anchor_ordinal=1, rate=1, period=Period.DAY, actual_ordinal=1, today=saturday
    )
    assert state.debt == 5


def test_a_future_track_accrues_nothing_and_counts_down() -> None:
    """The three parsha-weekly works begin at Shabbos Bereishis, 10 October 2026."""
    state = ledger_state(
        anchor_date=date(2026, 10, 10),
        anchor_ordinal=1,
        rate=1,
        period=Period.WEEK,
        actual_ordinal=0,
        today=date(2026, 9, 26),
        starts_on=date(2026, 10, 10),
    )
    assert state.debt == 0
    assert state.days_ahead == 0
    assert state.starts_in_days == 14
    assert not state.has_started


def test_a_track_accrues_from_its_start_date() -> None:
    state = ledger_state(
        anchor_date=date(2026, 10, 10),
        anchor_ordinal=1,
        rate=1,
        period=Period.WEEK,
        actual_ordinal=1,
        today=date(2026, 10, 24),
        starts_on=date(2026, 10, 10),
    )
    assert state.has_started
    assert state.debt == 2


def test_a_weekly_track_accrues_one_unit_a_week() -> None:
    common = {"anchor_date": ANCHOR, "anchor_ordinal": 1, "rate": 1, "period": Period.WEEK, "actual_ordinal": 1}
    assert ledger_state(**common, today=ANCHOR).debt == 0  # type: ignore[arg-type]
    assert ledger_state(**common, today=date(2026, 8, 30)).debt == 0  # type: ignore[arg-type]
    assert ledger_state(**common, today=date(2026, 8, 31)).debt == 1  # type: ignore[arg-type]
    assert ledger_state(**common, today=date(2026, 9, 21)).debt == 4  # type: ignore[arg-type]


# --- start dates --------------------------------------------------------------------------


def test_a_track_owes_its_first_unit_on_the_day_it_starts() -> None:
    """Shabbos Bereishis is a learning day: the Bereishis sicha is due on it, not a week later."""
    state = ledger_state(
        anchor_date=date(2026, 10, 10),
        anchor_ordinal=1,
        rate=1,
        period=Period.WEEK,
        actual_ordinal=0,
        today=date(2026, 10, 10),
        starts_on=date(2026, 10, 10),
        total=54,
    )
    assert state.scheduled == 1
    assert state.debt == 1
    assert state.has_started


def test_the_day_before_it_starts_it_owes_nothing_and_counts_down() -> None:
    state = ledger_state(
        anchor_date=date(2026, 10, 10),
        anchor_ordinal=1,
        rate=1,
        period=Period.WEEK,
        actual_ordinal=0,
        today=date(2026, 10, 9),
        starts_on=date(2026, 10, 10),
        total=54,
    )
    assert state.debt == 0
    assert state.starts_in_days == 1
    assert not state.has_started


def test_an_anchor_stranded_before_the_start_date_does_not_invent_debt() -> None:
    """The bug this replaces: a track anchored in August but starting in October opened seven
    units behind on its first morning. An older ledger export can still carry such a row."""
    state = ledger_state(
        anchor_date=date(2026, 8, 24),
        anchor_ordinal=1,
        rate=1,
        period=Period.WEEK,
        actual_ordinal=0,
        today=date(2026, 10, 10),
        starts_on=date(2026, 10, 10),
        total=54,
    )
    assert state.debt == 1


def test_a_started_track_accrues_from_its_start_date() -> None:
    state = ledger_state(
        anchor_date=date(2026, 9, 8),
        anchor_ordinal=1,
        rate=1,
        period=Period.DAY,
        actual_ordinal=0,
        today=date(2026, 9, 11),
        starts_on=date(2026, 9, 8),
        total=1707,
    )
    assert state.scheduled == 4
    assert state.debt == 4


def test_credit_banked_before_a_track_starts_survives() -> None:
    """Learning ahead during the countdown is banked, not confiscated when the day arrives."""
    state = ledger_state(
        anchor_date=date(2026, 10, 10),
        anchor_ordinal=1,
        rate=1,
        period=Period.WEEK,
        actual_ordinal=3,
        today=date(2026, 10, 10),
        starts_on=date(2026, 10, 10),
        total=54,
    )
    assert state.debt == -2
    assert state.days_ahead == 2


def test_the_countdown_state_reports_itself() -> None:
    state = LedgerState.not_started(
        anchor_ordinal=5, actual_ordinal=2, starts_on=date(2026, 10, 10), today=date(2026, 9, 1)
    )
    assert (state.scheduled, state.actual, state.debt, state.days_ahead) == (5, 2, 0, 0)
    assert state.starts_in_days == 39
    assert not state.has_started
