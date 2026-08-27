"""The span of days a Stats request actually covers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

MIN_WINDOW_DAYS = 1
MAX_WINDOW_DAYS = 371


@dataclass(frozen=True, slots=True)
class Window:
    """A closed range of days, never empty and never longer than the ledger has existed."""

    start: date
    end: date
    requested_days: int

    @property
    def days(self) -> list[date]:
        return [self.start + timedelta(days=offset) for offset in range((self.end - self.start).days + 1)]

    @property
    def length(self) -> int:
        return (self.end - self.start).days + 1


def window_for(*, on: date, requested_days: int, earliest_origin: date | None) -> Window:
    """Clamp a requested window to the ledger's own age.

    A ninety-column grid with two lit columns is not a report, it is an apology. The outer ``min``
    is what makes the length impossible to invert: however early the origin or however late the
    day, ``start`` can never pass ``end``.
    """
    asked = max(MIN_WINDOW_DAYS, min(requested_days, MAX_WINDOW_DAYS))
    floor = on - timedelta(days=asked - 1)
    start = floor if earliest_origin is None else max(floor, earliest_origin)
    return Window(start=min(on, start), end=on, requested_days=asked)
