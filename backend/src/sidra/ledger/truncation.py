"""What one backwards correction did."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Truncation:
    """The shape of a correction, for the toast that reports it."""

    from_ordinal: int
    """Where the track stood before."""

    to_ordinal: int
    """Where it stands now."""

    removed_advances: int
    """Rows deleted outright. A row trimmed rather than deleted is not counted here."""

    removed_units: int
    """How far the position dropped, which is what he wants told: ``from_ordinal - to_ordinal``."""
