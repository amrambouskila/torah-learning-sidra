"""Move the day a track's schedule began counting.

The seeder stamps ``anchor_date`` with the day it ran, and bills that day as a learning day. When
the position it was given was already true *for* that day, the day is billed twice and the schedule
runs one period ahead of the truth for ever after.

This is the operand to move when the error is the start rather than the position: every day before
the new origin falls back to a flat ``anchor_ordinal`` in ``stats/scheduled_series.py``, so the
opening debt the ledger was seeded with survives the correction intact. Shifting the ordinal
instead would restate it.
"""

from __future__ import annotations

from datetime import date

from sidra.db.models import Track


def reanchor(track: Track, started_on: date) -> None:
    """Set the origin, keeping ``starts_on`` alongside it when the track has one.

    ``effective_anchor`` takes the later of the pair, so moving only one of them would be a silent
    no-op in one direction and would break the conforming-row invariant in the other.
    """
    track.anchor_date = started_on
    if track.starts_on is not None:
        track.starts_on = started_on
