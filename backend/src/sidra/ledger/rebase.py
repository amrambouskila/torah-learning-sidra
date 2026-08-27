"""Move a track's schedule onto a new start date.

Setting a start date rebases the calibration pair: ``anchor_date`` moves onto the chosen day, so
the schedule begins there rather than wherever the track was seeded. Without that, declaring a
start seven weeks out would open the track seven units behind on its first morning.

The ordinal is the subtle half. It is rewritten only on the **first** declaration, where the
caller has already established nothing has been learned. On a later move, or on a clear, it is
carried forward untouched -- otherwise a track advanced during its own countdown would have its
banked credit quietly confiscated, and banking credit is half the model.
"""

from __future__ import annotations

from datetime import date

from sidra.db.models import Track


def rebase_start(track: Track, starts_on: date | None, *, actual_ordinal: int, today: date) -> None:
    """Apply a new start date, or clear it, keeping the anchor coherent either way."""
    if starts_on is None:
        # A future anchor with no gate in front of it would raise on every later read, so pull it
        # to today. A past anchor belongs to a schedule that has really been running: leave it, or
        # every unit accrued since would be silently forgiven.
        if track.anchor_date > today:
            track.anchor_date = today
        track.starts_on = None
        return

    first_declaration = track.starts_on is None
    track.anchor_date = starts_on
    track.starts_on = starts_on
    if first_declaration:
        # The start day is a learning day, so one period's worth is due on it.
        track.anchor_ordinal = actual_ordinal + track.rate
