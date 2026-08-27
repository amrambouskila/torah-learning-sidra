from __future__ import annotations

import uuid

from pydantic import BaseModel

from sidra.api.models.track_row import TrackRow


class AdvanceResult(BaseModel):
    """What one advance did, and the track as it now stands."""

    advance_id: uuid.UUID | None
    """None when the request was a replay and nothing was written."""

    resolved_ordinal: int
    """Where the request resolved to, written or not.

    On a replay ``from_ordinal`` and ``to_ordinal`` both report where he already was, which says
    nothing about where he aimed -- so a caller could not describe a backwards reference without
    resolving it a second time."""

    from_ordinal: int
    to_ordinal: int
    unit_count: int
    was_replay: bool
    track: TrackRow
