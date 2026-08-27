"""The ledger written out before a correction deletes part of it."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.db.models import Advance, Track
from sidra.ledger.ledger_file import LEDGER_PATH, read_ledger
from sidra.ledger.safety_copy import SAFETY_COPY_PATH, write_safety_copy
from tests.db.test_seed_tracks import AS_OF, HEBREW_AS_OF, _seed, _track

pytestmark = pytest.mark.integration

JEREMIAH_44 = 120
JEREMIAH_49 = 125


async def _neviim(session: AsyncSession) -> Track:
    await _seed(session)
    return await _track(session, "Neviim")


def test_it_is_never_the_portable_export() -> None:
    """That file is what the launcher imports into an empty ledger. Writing the pre-correction
    state there would leave it one correction stale the moment the correction succeeded."""
    assert SAFETY_COPY_PATH != LEDGER_PATH
    assert SAFETY_COPY_PATH.parent == LEDGER_PATH.parent


async def test_it_writes_a_ledger_the_import_path_accepts(db_session: AsyncSession, tmp_path: Path) -> None:
    track = await _neviim(db_session)
    out = tmp_path / "before.json"

    advances = await write_safety_copy(db_session, out)

    document = read_ledger(out)
    assert advances == len(document.advances)
    assert any(record.name_en == track.name_en for record in document.tracks)


async def test_it_holds_the_row_a_correction_is_about_to_delete(db_session: AsyncSession, tmp_path: Path) -> None:
    """The whole point: what it captures is the state that is about to stop existing."""
    track = await _neviim(db_session)
    db_session.add(
        Advance(
            track_id=track.id,
            from_ordinal=JEREMIAH_44,
            to_ordinal=JEREMIAH_49,
            unit_count=JEREMIAH_49 - JEREMIAH_44,
            occurred_at=datetime(AS_OF.year, AS_OF.month, AS_OF.day, 12, tzinfo=UTC),
            hebrew_date=HEBREW_AS_OF,
            note=None,
        )
    )
    await db_session.flush()
    out = tmp_path / "before.json"

    await write_safety_copy(db_session, out)

    document = read_ledger(out)
    assert any(record.to_ordinal == JEREMIAH_49 for record in document.advances)
