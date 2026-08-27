"""Move a track's actual position backwards by rewriting the rows behind it.

``actual_ordinal`` is ``MAX(Advance.to_ordinal)``, and every consumer of the ledger -- Stats, the
streak, the pace projection, the rail, both ceilings -- is built on advances that only ever move
forward. Rather than teach all of them about backwards motion, a correction makes the rows tell the
truth: what was never learned stops being recorded.

The synthetic opening row in the last branch is the seeder's own idiom, and it is what lets a
correction pass below the earliest row's ``from_ordinal`` instead of treating it as a floor.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.db.models import Advance, Track
from sidra.ledger.seed_tracks import SEED_NOTE, actual_ordinal
from sidra.ledger.truncation import Truncation


async def truncate_to(session: AsyncSession, track: Track, target: int) -> Truncation:
    """Rewrite the track's advances so its position is exactly ``target``.

    Rows are contiguous -- each opens where the previous closed -- so a target inside any row's
    span is trimmed by the second branch and ends there. The third branch is therefore reached only
    once every row has gone, which is why ``doomed`` is never empty when it runs.
    """
    before = await actual_ordinal(session, track)
    rows = list(
        (await session.execute(select(Advance).where(Advance.track_id == track.id).order_by(Advance.from_ordinal)))
        .scalars()
        .all()
    )

    doomed = [row for row in rows if row.from_ordinal >= target]
    survivors = [row for row in rows if row.from_ordinal < target]
    for row in doomed:
        await session.delete(row)

    straddler = next((row for row in survivors if row.to_ordinal > target), None)
    if straddler is not None:
        straddler.to_ordinal = target
        straddler.unit_count = target - straddler.from_ordinal
    elif target > 0 and not any(row.to_ordinal == target for row in survivors):
        opening = max(0, target - track.rate)
        session.add(
            Advance(
                track_id=track.id,
                from_ordinal=opening,
                to_ordinal=target,
                unit_count=target - opening,
                occurred_at=doomed[0].occurred_at,
                hebrew_date=doomed[0].hebrew_date,
                note=SEED_NOTE,
            )
        )

    await session.flush()
    return Truncation(
        from_ordinal=before,
        to_ordinal=target,
        removed_advances=len(doomed),
        removed_units=before - target,
    )
