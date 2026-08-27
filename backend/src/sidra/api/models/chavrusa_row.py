from __future__ import annotations

import uuid

from pydantic import BaseModel

from sidra.api.models.session_row import SessionRow
from sidra.api.models.track_row import TrackRow


class ChavrusaRow(BaseModel):
    """One learning partner, their tracks, and the sessions behind them."""

    id: uuid.UUID
    name: str
    notes: str | None
    days_stale: int | None
    """Days since the most recent session across all their tracks. None if they have never met."""

    tracks: list[TrackRow]
    sessions: list[SessionRow]
