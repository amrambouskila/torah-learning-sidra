"""Which masechtos sit behind the hilchos a chavrusa track is currently in.

This is what drives the Gemara queue. Rabbi Jacob's Mishneh Torah runs in the Rambam's own order,
and the matching Gemara is pulled across from wherever in Shas it happens to live.

The answer is a distribution, not a recommendation, and inferred edges are marked as such: a link
bridged through Tur's siman numbering is an inference, and presenting it as a citation would
misrepresent the apparatus.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.alignment.aggregate import TALMUD_CATEGORY, masechta_of
from sidra.api.deps import get_session
from sidra.api.models.alignment_row import AlignmentRow
from sidra.api.track_rows import track_or_404
from sidra.db.models import TopicLink
from sidra.db.seed import INFERRED_CONFIDENCE
from sidra.ledger.position import position_at
from sidra.ledger.seed_tracks import actual_ordinal

router = APIRouter(prefix="/api/alignment", tags=["alignment"])

MAX_ROWS = 25


@router.get("/{track_id}", response_model=list[AlignmentRow])
async def get_alignment(
    track_id: uuid.UUID,
    limit: int = Query(default=MAX_ROWS, ge=1, le=MAX_ROWS),
    session: AsyncSession = Depends(get_session),
) -> list[AlignmentRow]:
    """Rank the masechtos tied to the work the track currently stands in."""
    track = await track_or_404(session, track_id)
    try:
        ordinal = await actual_ordinal(session, track)
        if ordinal < 1:
            return []
        work_ref_title = (await position_at(session, track, ordinal)).work_ref_title
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    prefix = f"{work_ref_title} "
    rows = (
        (
            await session.execute(
                select(TopicLink).where(TopicLink.from_ref.startswith(prefix) | TopicLink.to_ref.startswith(prefix))
            )
        )
        .scalars()
        .all()
    )

    counts: dict[str, int] = {}
    inferred: dict[str, int] = {}
    for link in rows:
        if link.from_ref.startswith(prefix) and link.to_category == TALMUD_CATEGORY:
            citation = link.to_ref
        elif link.to_ref.startswith(prefix) and link.from_category == TALMUD_CATEGORY:
            citation = link.from_ref
        else:
            continue
        masechta = masechta_of(citation)
        counts[masechta] = counts.get(masechta, 0) + 1
        if link.confidence == INFERRED_CONFIDENCE:
            inferred[masechta] = inferred.get(masechta, 0) + 1

    total = sum(counts.values())
    if total == 0:
        return []

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return [
        AlignmentRow(
            masechta=masechta,
            links=links,
            share=links / total,
            # Marked inferred only when every edge behind the row is one: a masechta with real
            # citations plus a few bridged ones is still a cited match.
            is_inferred=inferred.get(masechta, 0) == links,
        )
        for masechta, links in ranked
    ]
