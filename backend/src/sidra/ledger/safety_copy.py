"""The ledger as it stood immediately before a correction deleted part of it.

Correcting a position backwards is the only operation in the app that destroys recorded learning,
and there is no undo of an undo. This writes the whole ledger out first, so the one destructive
gesture is always recoverable by the import path that already exists.

Deliberately **not** ``data/ledger.json``. That file is the portable export the launcher imports
into an empty ledger, so writing the pre-correction state there would leave it one correction stale
the moment the correction succeeded -- and a folder copied to another machine would restore exactly
the state he had just corrected away.

To recover:

    uv run sidra-db import --source data/ledger.before-correction.json
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from sidra.ledger.ledger_file import LEDGER_PATH, write_ledger
from sidra.ledger.transfer import export_ledger

SAFETY_COPY_PATH = LEDGER_PATH.with_name("ledger.before-correction.json")
"""Beside the portable export, and never it."""


async def write_safety_copy(session: AsyncSession, path: Path = SAFETY_COPY_PATH) -> int:
    """Write the ledger as it stands now. Returns how many advances it holds.

    Only ever one deep: a second correction overwrites the first, which is the right depth for the
    thing it protects against -- a gesture noticed immediately, one step back.
    """
    document = await export_ledger(session)
    write_ledger(path, document)
    return len(document.advances)
