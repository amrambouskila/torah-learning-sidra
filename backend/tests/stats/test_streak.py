from __future__ import annotations

from datetime import date

from sidra.stats.streak import current_run, longest_run

D = date


def test_no_days_is_no_streak() -> None:
    assert longest_run([]) == 0
    assert current_run([], on=D(2026, 8, 26)) == 0


def test_the_longest_run_ignores_gaps() -> None:
    days = [D(2026, 8, 1), D(2026, 8, 2), D(2026, 8, 3), D(2026, 8, 10), D(2026, 8, 11)]
    assert longest_run(days) == 3


def test_a_repeated_day_counts_once() -> None:
    assert longest_run([D(2026, 8, 1), D(2026, 8, 1), D(2026, 8, 2)]) == 2


def test_a_streak_running_to_today_counts_today() -> None:
    assert current_run([D(2026, 8, 25), D(2026, 8, 26)], on=D(2026, 8, 26)) == 2


def test_a_streak_that_ends_yesterday_still_stands() -> None:
    """A streak resetting at midnight would describe the same ledger differently at 23:00 and at
    09:00 -- a lie about the ledger rather than a fact about the learning."""
    assert current_run([D(2026, 8, 24), D(2026, 8, 25)], on=D(2026, 8, 26)) == 2


def test_a_streak_broken_for_two_days_is_over() -> None:
    assert current_run([D(2026, 8, 23), D(2026, 8, 24)], on=D(2026, 8, 26)) == 0
