"""The anchor ordinal that would put a track's scheduled position where it should be today.

Every schedule in the app has the shape ``anchor_ordinal + f(calendar)`` -- flat-rate in
``schedule.py``, calendar-driven in ``parsha_schedule.py`` -- so one subtraction serves both
without branching on the kind, and it is exact at any delta rather than quantised to whole periods
the way moving the anchor date is.

Pure, and deliberately so: the result can be out of range, and a caller that had already written it
to the track would be holding a rejected value in a live session. It computes; the caller checks,
then assigns.

``anchor_date`` is no part of this. Moving it would make ``periods_elapsed`` raise for every
earlier day and take the Stats reconstruction with it -- that is the other operand, in
``reanchor.py``.
"""

from __future__ import annotations

from sidra.db.models import Track


def recalibrated_anchor(track: Track, desired: int, scheduled_today: int) -> int:
    """The anchor that puts today's scheduled ordinal at ``desired``, leaving the calendar alone."""
    return track.anchor_ordinal + desired - scheduled_today
