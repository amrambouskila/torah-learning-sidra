"""How far forward a track can be moved, and how far its rail may be drawn."""

from __future__ import annotations

CYCLES_AHEAD = 1
"""A cycle track can be moved at most one whole turn past its furthest marker.

Far enough to record any session and to catch up from any debt, and short of the unbounded runway
a cumulative ordinal would otherwise offer. Undoing one is possible now -- ``PUT /position`` --
but it is deliberate, confirmed and destructive, so the ceiling still stands between a mistyped
ordinal and a year of phantom learning. It is simply no longer the only thing that does.
"""


def reachable_ceiling(*, actual: int, scheduled: int | None, total: int, cycle_length: int | None) -> int:
    """The furthest ordinal that may be advanced to, offered on the rail, or drawn.

    One function for all three, because three ceilings that disagree let a picker offer a unit the
    endpoint then refuses.
    """
    if cycle_length is None:
        return total
    furthest = max(actual, scheduled or 0, 1)
    return furthest + CYCLES_AHEAD * cycle_length
