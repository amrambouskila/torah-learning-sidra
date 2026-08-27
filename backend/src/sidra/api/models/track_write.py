from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class TrackStartUpdate(BaseModel):
    """Set, move or clear the day a track's schedule begins.

    The client sends intent, never arithmetic: it says which day, and the server rebases the
    track's anchor onto it. An explicit ``null`` clears the start date.

    ``extra="forbid"`` because with a single field a mistyped key would otherwise be a silent
    no-op that still answered 200.
    """

    model_config = ConfigDict(extra="forbid")

    starts_on: date | None = None

    forgive: bool = False
    """Acknowledge that setting this date clears a debt the track has genuinely accrued.

    Rebasing is refused without it whenever a positive debt would be erased, so a backlog
    cannot be wiped by accident. A track that owes nothing needs no acknowledgement."""
