"""Working out the opening position that puts today's scheduled ordinal where it should be."""

from __future__ import annotations

from datetime import date

import pytest

from sidra.ledger.recalibrate import recalibrated_anchor
from tests.ledger.test_reanchor import _track


@pytest.mark.parametrize(
    ("anchor_ordinal", "scheduled_today", "desired", "expected"),
    [
        (260, 263, 262, 259),  # the Neviim case, one back
        (260, 263, 263, 260),  # already right, a no-op
        (260, 263, 270, 267),  # forwards is just as legal
        (100, 118, 100, 82),  # a rate-3 weekly track, six periods in
        (2, 5, 1, -2),  # out of range, and returned rather than refused: the caller checks
    ],
)
def test_the_anchor_absorbs_the_whole_difference(
    anchor_ordinal: int, scheduled_today: int, desired: int, expected: int
) -> None:
    track = _track(anchor=date(2026, 8, 24), ordinal=anchor_ordinal)
    assert recalibrated_anchor(track, desired, scheduled_today) == expected


def test_it_writes_nothing() -> None:
    """The result can be out of range, so a caller holding it on the track would be holding a
    value it is about to refuse. It computes; the router checks, then assigns."""
    track = _track(anchor=date(2026, 8, 24), ordinal=260)
    recalibrated_anchor(track, 262, 263)
    assert track.anchor_ordinal == 260
    assert track.anchor_date == date(2026, 8, 24)
