from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MaintenanceStatus(BaseModel):
    """What the Maintenance screen shows before he presses anything."""

    catalog_seeded: bool
    ledger_seeded: bool
    works: int
    stored_units: int
    tracks: int
    advances: int

    ledger_exported_at: datetime | None
    """When ``data/ledger.json`` was last written. None when it has never been."""

    safety_copy_at: datetime | None
    """When a correction last wrote its safety copy. None when none ever has."""
