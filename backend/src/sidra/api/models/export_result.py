from __future__ import annotations

from pydantic import BaseModel


class ExportResult(BaseModel):
    """What one ledger export wrote."""

    path: str
    tracks: int
    advances: int
    chavrusas: int
    tags: int
    calendar_days: int
