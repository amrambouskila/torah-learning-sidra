"""How long one turn of a track's cycle is, when the track repeats at all."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from sidra.db.models import Track
from sidra.ledger.cycle_works import cycle_ref_titles
from sidra.ledger.position import track_total, works_for_track


async def cycle_length(session: AsyncSession, track: Track) -> int | None:
    """The units in one turn, or None when the track runs once and stops.

    Every work the track runs through must repeat, not merely one of them: a track that read the
    Chumash and then went on to something else would not return to Bereshit.
    """
    works = await works_for_track(session, track)
    repeating = cycle_ref_titles()
    if not works or any(work.ref_title not in repeating for work in works):
        return None
    return await track_total(session, track)
