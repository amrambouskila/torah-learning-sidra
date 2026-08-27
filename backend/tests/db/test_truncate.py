"""Rewriting advance rows so the ledger's position tells the truth."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.db.models import Advance, Track
from sidra.ledger.seed_tracks import SEED_NOTE, actual_ordinal
from sidra.ledger.truncate import truncate_to
from tests.db.test_seed_tracks import AS_OF, HEBREW_AS_OF, _seed, _track

pytestmark = pytest.mark.integration

JEREMIAH_43 = 119
JEREMIAH_44 = 120
JEREMIAH_48 = 124
JEREMIAH_49 = 125


async def _neviim(session: AsyncSession) -> Track:
    """The seeded Neviim track, standing at Jeremiah 44 with one opening row."""
    await _seed(session)
    return await _track(session, "Neviim")


async def _advance(session: AsyncSession, track: Track, start: int, end: int) -> None:
    session.add(
        Advance(
            track_id=track.id,
            from_ordinal=start,
            to_ordinal=end,
            unit_count=end - start,
            occurred_at=datetime(AS_OF.year, AS_OF.month, AS_OF.day, 12, tzinfo=UTC),
            hebrew_date=HEBREW_AS_OF,
            note=None,
        )
    )
    await session.flush()


async def _rows(session: AsyncSession, track: Track) -> list[Advance]:
    result = await session.execute(select(Advance).where(Advance.track_id == track.id).order_by(Advance.from_ordinal))
    return list(result.scalars().all())


async def test_a_straddling_row_is_trimmed_rather_than_deleted(db_session: AsyncSession) -> None:
    """The everyday correction: he said Jeremiah 49 and meant Jeremiah 48."""
    track = await _neviim(db_session)
    await _advance(db_session, track, JEREMIAH_44, JEREMIAH_49)

    result = await truncate_to(db_session, track, JEREMIAH_48)

    assert await actual_ordinal(db_session, track) == JEREMIAH_48
    assert result.from_ordinal == JEREMIAH_49
    assert result.to_ordinal == JEREMIAH_48
    assert result.removed_units == 1
    assert result.removed_advances == 0
    rows = await _rows(db_session, track)
    assert [(row.from_ordinal, row.to_ordinal, row.unit_count) for row in rows] == [
        (JEREMIAH_43, JEREMIAH_44, 1),
        (JEREMIAH_44, JEREMIAH_48, 4),
    ]


async def test_a_row_that_already_ends_at_the_target_is_left_alone(db_session: AsyncSession) -> None:
    """No synthetic row is written when the ledger can already say where he is."""
    track = await _neviim(db_session)
    await _advance(db_session, track, JEREMIAH_44, JEREMIAH_49)

    result = await truncate_to(db_session, track, JEREMIAH_44)

    assert await actual_ordinal(db_session, track) == JEREMIAH_44
    assert result.removed_advances == 1
    assert result.removed_units == 5
    rows = await _rows(db_session, track)
    assert [(row.from_ordinal, row.to_ordinal) for row in rows] == [(JEREMIAH_43, JEREMIAH_44)]


async def test_correcting_below_the_opening_row_writes_a_new_one(db_session: AsyncSession) -> None:
    """Without this the earliest row's from_ordinal would be a floor no correction could pass."""
    track = await _neviim(db_session)
    await _advance(db_session, track, JEREMIAH_44, JEREMIAH_49)

    result = await truncate_to(db_session, track, JEREMIAH_43)

    assert await actual_ordinal(db_session, track) == JEREMIAH_43
    assert result.removed_advances == 2
    rows = await _rows(db_session, track)
    assert len(rows) == 1
    assert (rows[0].from_ordinal, rows[0].to_ordinal, rows[0].unit_count) == (JEREMIAH_43 - 1, JEREMIAH_43, 1)
    # The seeder's note, so Stats keeps excluding it from days learned.
    assert rows[0].note == SEED_NOTE
    # The date of the earliest row it replaces, so history gains no entry dated today.
    assert rows[0].occurred_at.date() == AS_OF
    assert rows[0].hebrew_date == HEBREW_AS_OF


async def test_correcting_to_zero_leaves_the_track_unopened(db_session: AsyncSession) -> None:
    track = await _neviim(db_session)
    await _advance(db_session, track, JEREMIAH_44, JEREMIAH_49)

    result = await truncate_to(db_session, track, 0)

    assert await actual_ordinal(db_session, track) == 0
    assert await _rows(db_session, track) == []
    assert result.to_ordinal == 0
    assert result.removed_units == JEREMIAH_49
