"""Moving the day a track's schedule began counting."""

from __future__ import annotations

from datetime import date

from sidra.db.models import Track
from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.reanchor import reanchor
from sidra.ledger.schedule import periods_elapsed, scheduled_ordinal
from sidra.ledger.track_kind import TrackKind


def _track(*, anchor: date, ordinal: int, starts_on: date | None = None) -> Track:
    return Track(
        name_en="Neviim",
        name_he="נביאים",
        category=Category.DAILY,
        kind=TrackKind.CORPUS,
        corpus_id="neviim",
        rate=1,
        period=Period.DAY,
        anchor_date=anchor,
        anchor_ordinal=ordinal,
        starts_on=starts_on,
    )


def test_it_moves_the_anchor_date() -> None:
    track = _track(anchor=date(2026, 8, 24), ordinal=260)
    reanchor(track, date(2026, 8, 25))
    assert track.anchor_date == date(2026, 8, 25)
    assert track.anchor_ordinal == 260
    assert track.starts_on is None


def test_the_neviim_case_lands_on_jeremiah_49() -> None:
    """One day later means one fewer period billed, which is the whole correction."""
    track = _track(anchor=date(2026, 8, 24), ordinal=260)
    today = date(2026, 8, 27)
    assert scheduled_ordinal(track.anchor_ordinal, 1, periods_elapsed(track.anchor_date, today, Period.DAY)) == 263

    reanchor(track, date(2026, 8, 25))

    assert scheduled_ordinal(track.anchor_ordinal, 1, periods_elapsed(track.anchor_date, today, Period.DAY)) == 262


def test_a_start_date_moves_with_the_anchor() -> None:
    """``effective_anchor`` takes the later of the two, so leaving one behind would be a no-op."""
    track = _track(anchor=date(2026, 9, 5), ordinal=1, starts_on=date(2026, 9, 5))
    reanchor(track, date(2026, 9, 7))
    assert track.anchor_date == date(2026, 9, 7)
    assert track.starts_on == date(2026, 9, 7)
