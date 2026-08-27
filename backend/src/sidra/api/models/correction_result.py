from __future__ import annotations

from pydantic import BaseModel

from sidra.api.models.track_row import TrackRow


class CorrectionResult(BaseModel):
    """What one backwards correction did, and the track as it now stands."""

    from_ordinal: int
    to_ordinal: int

    removed_units: int
    """How far the position dropped, which is what the toast reports."""

    removed_advances: int
    """Rows deleted outright. A row trimmed rather than deleted is not counted."""

    moved: bool
    """False when the destination was already the position and nothing was written."""

    track: TrackRow
