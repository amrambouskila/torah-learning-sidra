from __future__ import annotations

from datetime import date, timedelta

import pytest

from sidra.stats.window import MAX_WINDOW_DAYS, window_for

ON = date(2026, 8, 26)


def test_the_window_is_clamped_to_the_ledgers_own_age() -> None:
    """A ninety-column grid with two lit columns is not a report, it is an apology."""
    span = window_for(on=ON, requested_days=90, earliest_origin=date(2026, 8, 24))
    assert span.length == 3
    assert span.requested_days == 90
    assert span.days == [date(2026, 8, 24), date(2026, 8, 25), ON]


def test_a_ledger_older_than_the_window_gets_the_window_it_asked_for() -> None:
    span = window_for(on=ON, requested_days=7, earliest_origin=date(2020, 1, 1))
    assert span.length == 7


@pytest.mark.parametrize("requested", [-5, 0, 1, MAX_WINDOW_DAYS, MAX_WINDOW_DAYS + 1000])
def test_the_length_can_never_be_zero_or_negative(requested: int) -> None:
    """The recorded defect. Whatever is asked for, and whatever the origin, start cannot pass end."""
    span = window_for(on=ON, requested_days=requested, earliest_origin=None)
    assert span.length >= 1
    assert span.start <= span.end


def test_an_origin_in_the_future_cannot_invert_the_window() -> None:
    """Several tracks have not begun. Their origins must not be able to push start past today."""
    span = window_for(on=ON, requested_days=30, earliest_origin=ON + timedelta(days=45))
    assert span.length == 1
    assert span.days == [ON]


def test_a_ledger_with_no_begun_track_still_reports_a_day() -> None:
    span = window_for(on=ON, requested_days=30, earliest_origin=None)
    assert span.length == 30
