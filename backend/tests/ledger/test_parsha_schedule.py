from __future__ import annotations

from datetime import date, timedelta

import pytest

from sidra.calendar.calendar_day import CalendarDay
from sidra.ledger.parsha_schedule import (
    aliyot_accrued,
    parsha_aliyah_state,
    parsha_weekly_state,
    parshiyos_accrued,
)

ANCHOR = date(2026, 10, 10)  # Shabbos Bereishis 5787.


def _week(start: date, *names: str) -> list[CalendarDay]:
    """Seven consecutive days all carrying the same parsha, as Sefaria reports a week."""
    return [
        CalendarDay(
            civil_date=start + timedelta(days=offset),
            hebrew_date="x",
            parsha_en=names,
            parsha_he=tuple(f"he-{name}" for name in names),
            is_yom_tov=False,
        )
        for offset in range(7)
    ]


def _blank(on: date) -> CalendarDay:
    return CalendarDay(civil_date=on, hebrew_date="x", parsha_en=(), parsha_he=(), is_yom_tov=True)


# --- accrual primitives -------------------------------------------------------------------


def test_a_normal_week_supplies_seven_aliyot() -> None:
    assert aliyot_accrued(_week(ANCHOR, "Bereshit")) == 7


def test_a_combined_week_supplies_fourteen_aliyot() -> None:
    """Two a day. The text is not halved to fit the week."""
    assert aliyot_accrued(_week(ANCHOR, "Nitzavim", "Vayeilech")) == 14


def test_aliyot_accrue_one_per_day_within_a_week() -> None:
    week = _week(ANCHOR, "Bereshit")
    assert [aliyot_accrued(week[: n + 1]) for n in range(7)] == [1, 2, 3, 4, 5, 6, 7]


def test_a_combined_week_accrues_two_per_day() -> None:
    week = _week(ANCHOR, "Nitzavim", "Vayeilech")
    assert [aliyot_accrued(week[: n + 1]) for n in range(7)] == [2, 4, 6, 8, 10, 12, 14]


def test_a_day_the_calendar_gives_no_parsha_accrues_nothing() -> None:
    """Under-accruing is the safe direction: it never invents a debt out of a gap in the source."""
    assert aliyot_accrued([_blank(ANCHOR)]) == 0
    assert aliyot_accrued([*_week(ANCHOR, "Bereshit"), _blank(ANCHOR + timedelta(days=7))]) == 7


def test_a_normal_week_supplies_one_parsha() -> None:
    assert parshiyos_accrued(_week(ANCHOR, "Bereshit")) == 1


def test_a_combined_week_supplies_two_parshiyos() -> None:
    """Fifty-four parshiyos across roughly fifty weeks only works if combined weeks count twice."""
    assert parshiyos_accrued(_week(ANCHOR, "Nitzavim", "Vayeilech")) == 2


def test_a_parsha_counts_once_however_many_days_of_it_have_passed() -> None:
    week = _week(ANCHOR, "Bereshit")
    assert [parshiyos_accrued(week[: n + 1]) for n in range(7)] == [1] * 7


def test_consecutive_weeks_accrue_one_each() -> None:
    days = [*_week(ANCHOR, "Bereshit"), *_week(ANCHOR + timedelta(days=7), "Noach")]
    assert parshiyos_accrued(days) == 2
    assert aliyot_accrued(days) == 14


def test_a_parsha_name_that_comes_round_again_counts_again() -> None:
    """Counting distinct names would swallow every year of the cycle after the first."""
    days = [
        *_week(ANCHOR, "Bereshit"),
        *_week(ANCHOR + timedelta(days=7), "Noach"),
        *_week(ANCHOR + timedelta(days=14), "Bereshit"),
    ]
    assert parshiyos_accrued(days) == 3


def test_a_blank_day_does_not_split_a_parsha_run_in_two() -> None:
    week = _week(ANCHOR, "Bereshit")
    days = [*week[:3], _blank(ANCHOR + timedelta(days=3)), *week[4:]]
    assert parshiyos_accrued(days) == 1


def test_an_empty_range_raises() -> None:
    with pytest.raises(ValueError, match="no calendar days"):
        aliyot_accrued([])


def test_a_range_out_of_order_raises() -> None:
    """A gap or a repeat would silently mis-accrue, so the contiguity is checked, not assumed."""
    week = _week(ANCHOR, "Bereshit")
    with pytest.raises(ValueError, match="not contiguous"):
        parshiyos_accrued([week[0], week[2]])


# --- the aliyah track ---------------------------------------------------------------------


def test_seven_days_on_pace_owes_nothing() -> None:
    state = parsha_aliyah_state(anchor_ordinal=1, actual_ordinal=7, days=_week(ANCHOR, "Bereshit"))
    assert state.scheduled == 7
    assert state.debt == 0
    assert not state.is_behind


def test_a_missed_day_accrues_one_unit_of_debt() -> None:
    state = parsha_aliyah_state(anchor_ordinal=1, actual_ordinal=6, days=_week(ANCHOR, "Bereshit"))
    assert state.debt == 1
    assert state.is_behind


def test_a_missed_day_in_a_combined_week_costs_two() -> None:
    state = parsha_aliyah_state(anchor_ordinal=1, actual_ordinal=12, days=_week(ANCHOR, "Nitzavim", "Vayeilech"))
    assert state.scheduled == 14
    assert state.debt == 2


def test_the_track_does_not_roll_past_an_unfinished_parsha() -> None:
    """A whole week missed leaves Amram still in Bereshit while the schedule has moved into Noach."""
    days = [*_week(ANCHOR, "Bereshit"), *_week(ANCHOR + timedelta(days=7), "Noach")]
    state = parsha_aliyah_state(anchor_ordinal=1, actual_ordinal=1, days=days)
    assert state.actual == 1
    assert state.scheduled == 14
    assert state.debt == 13


def test_learning_ahead_banks_rather_than_reading_as_negative_debt() -> None:
    state = parsha_aliyah_state(anchor_ordinal=1, actual_ordinal=10, days=_week(ANCHOR, "Bereshit"))
    assert state.debt == -3
    assert state.days_ahead == 3


def test_a_combined_week_banks_in_days_not_aliyot() -> None:
    """Two aliyot ahead in a fourteen-aliyah week is one day ahead, not two."""
    state = parsha_aliyah_state(anchor_ordinal=1, actual_ordinal=16, days=_week(ANCHOR, "Nitzavim", "Vayeilech"))
    assert state.debt == -2
    assert state.days_ahead == 1


def test_a_finished_cycle_stops_accruing() -> None:
    days = [*_week(ANCHOR, "Bereshit"), *_week(ANCHOR + timedelta(days=7), "Noach")]
    state = parsha_aliyah_state(anchor_ordinal=1, actual_ordinal=10, days=days, total=10)
    assert state.scheduled == 10
    assert state.debt == 0


# --- the parsha-weekly tracks -------------------------------------------------------------
#
# These take a span that already begins at the track's effective anchor. The 'has it started'
# gate is track_state's job -- keeping a second copy here meant two gates that had to agree.


def test_one_unit_accrues_per_parsha_week() -> None:
    days = [*_week(ANCHOR, "Bereshit"), *_week(ANCHOR + timedelta(days=7), "Noach")]
    state = parsha_weekly_state(anchor_ordinal=1, actual_ordinal=2, days=days)
    assert state.scheduled == 2
    assert state.debt == 0


def test_a_combined_week_owes_two_units() -> None:
    """Likutei Sichot is indexed by parsha, and a combined week supplies two of them."""
    state = parsha_weekly_state(anchor_ordinal=1, actual_ordinal=1, days=_week(ANCHOR, "Nitzavim", "Vayeilech"))
    assert state.scheduled == 2
    assert state.debt == 1


def test_a_skipped_week_shows_as_one_behind() -> None:
    days = [*_week(ANCHOR, "Bereshit"), *_week(ANCHOR + timedelta(days=7), "Noach")]
    state = parsha_weekly_state(anchor_ordinal=1, actual_ordinal=1, days=days)
    assert state.debt == 1


def test_a_weekly_track_banks_whole_weeks() -> None:
    state = parsha_weekly_state(anchor_ordinal=1, actual_ordinal=4, days=_week(ANCHOR, "Bereshit"))
    assert state.debt == -3
    assert state.days_ahead == 3
