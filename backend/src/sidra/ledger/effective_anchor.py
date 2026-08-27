"""Where a track's schedule actually begins counting from.

``starts_on`` is not a gate bolted onto a schedule that was already running -- it is the day the
schedule begins to exist. Every writer that sets it also moves ``anchor_date`` onto it, so on a
conforming row the two are equal and this function is a no-op.

It exists as a seatbelt for the two writers that cannot be made to hold that invariant: a ledger
imported from an older export, and a hand-edited ``data/tracks.yaml``. A non-conforming row must
degrade to under-billing, never to phantom debt -- which is exactly what the bug this replaces
did: a track anchored in August but starting in October opened seven units behind on its first day.
"""

from __future__ import annotations

from datetime import date


def effective_anchor(anchor_date: date, starts_on: date | None) -> date:
    """The later of the two, because a schedule cannot have run before it began."""
    return anchor_date if starts_on is None else max(anchor_date, starts_on)
