"""One track's row in the Stats grid."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class TrackReport:
    """What one track did over the window, day by day.

    ``net`` is the ledger's own question: on each day, how much the schedule billed minus how much
    was learned. Positive means the gap opened that day; negative means it closed; zero means it
    held. A chavrusa track bills nothing, so its ``net`` is what it learned, negated.
    """

    track_id: str
    name_en: str
    name_he: str
    unit_singular: str
    unit_plural: str

    debt_now: int | None
    """None on a chavrusa track, which carries staleness rather than debt."""

    debt_then: int | None
    """The debt on the first day of the window, so the direction of travel is visible."""

    learned_units: int
    days_learned: int
    last_learned_on: date | None
    opened_on: date | None
    """The day the track was first advanced. None means never opened, which is not the same as
    opened and untouched -- the distinction is the most useful signal on a young ledger."""

    net: list[int]
    """One value per day of the window, in order."""
