from __future__ import annotations

from datetime import date

from sidra.ledger.effective_anchor import effective_anchor

AUGUST = date(2026, 8, 24)
OCTOBER = date(2026, 10, 10)


def test_a_track_with_no_start_date_counts_from_its_anchor() -> None:
    """The case that must not move: Gemara, Neviim and Chumash all take this branch."""
    assert effective_anchor(AUGUST, None) == AUGUST


def test_a_conforming_row_is_a_no_op() -> None:
    """Every writer sets anchor_date to starts_on, so the two are equal on a row we wrote."""
    assert effective_anchor(OCTOBER, OCTOBER) == OCTOBER


def test_a_start_date_later_than_the_anchor_wins() -> None:
    """The seatbelt: an older export or a hand-edited YAML can still carry an August anchor with
    an October start, and that must under-bill rather than invent seven weeks of debt."""
    assert effective_anchor(AUGUST, OCTOBER) == OCTOBER


def test_a_start_date_earlier_than_the_anchor_loses() -> None:
    """A schedule that has been running since August is not restarted by a past declaration."""
    assert effective_anchor(OCTOBER, AUGUST) == OCTOBER
