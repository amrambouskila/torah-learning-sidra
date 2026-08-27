"""Which masechta the code asks for next.

Amram's Gemara follows his Mishneh Torah rather than Shas order: whatever hilchos he is up to, the
Gemara he learns is the masechta that section draws on. When the Rambam crosses into a section no
masechta owns -- Teshuvah, Deos, Talmud Torah -- the Gemara does not move; he stays where he is
until a section with a real masechta arrives.

Read-only, and it reads the apparatus rather than inventing a curriculum: every pairing here is
Ein Mishpat's, and the share behind each one travels with it so a close call stays visible.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.deps import get_session
from sidra.api.models.position_model import PositionModel
from sidra.api.models.sequence_response import SequenceResponse
from sidra.api.models.sequence_stage import SequenceStage, SequenceWork
from sidra.api.track_rows import track_or_404
from sidra.db.models import Work
from sidra.ledger.position import position_at, works_for_track
from sidra.ledger.seed_tracks import actual_ordinal
from sidra.sequence.masechta_map import masechta_map
from sidra.sequence.stages import stages_from

router = APIRouter(prefix="/api", tags=["sequence"])

SEQUENCED_CORPORA = frozenset({"mishneh_torah", "shulchan_aruch"})
"""The codes Ein Mishpat maps. A Gemara or Chumash track has no apparatus to sequence."""

MAX_STAGES = 12


@router.get("/sequence/{track_id}", response_model=SequenceResponse)
async def get_sequence(
    track_id: uuid.UUID,
    limit: int = Query(default=MAX_STAGES, ge=1, le=MAX_STAGES),
    session: AsyncSession = Depends(get_session),
) -> SequenceResponse:
    """The masechtos ahead, in the order the code reaches them.

    No day parameter: the sequence follows where he stands, and where he stands is not a function
    of the calendar.
    """
    track = await track_or_404(session, track_id)

    works = await works_for_track(session, track)
    corpus = works[0].corpus_id if works else None
    if corpus not in SEQUENCED_CORPORA:
        raise HTTPException(
            status_code=422,
            detail=f"{track.name_en} is not a code track; only the Rambam and the Shulchan Aruch are sequenced",
        )

    ordinal = await actual_ordinal(session, track)
    total = sum(work.unit_count for work in works)
    here = await position_at(session, track, ordinal) if 1 <= ordinal <= total else None

    ahead, done_in_current = _from_here(works, ordinal)
    found = await masechta_map(session, corpus)
    hebrew = await _masechta_hebrew(session)

    stages = stages_from(ahead, found)[:limit]
    rows: list[SequenceStage] = []
    distance = -done_in_current
    seen: set[str] = set()
    for index, stage in enumerate(stages):
        name = stage.masechta
        rows.append(
            SequenceStage(
                masechta_en=name,
                masechta_he=None if name is None else hebrew.get(name),
                share=None if stage.dominance is None else stage.dominance.share,
                links=None if stage.dominance is None else stage.dominance.links,
                runner_up=None if stage.dominance is None else stage.dominance.runner_up,
                works=[
                    SequenceWork(ref_title=work.ref_title, title_he=work.title_he, halachos=work.unit_count)
                    for work in stage.works
                ],
                halachos_in_stage=stage.halachos,
                halachos_until=max(0, distance),
                is_current=index == 0,
                seen_before=name is not None and name in seen,
            )
        )
        if name is not None:
            seen.add(name)
        distance += stage.halachos

    return SequenceResponse(
        track_id=track.id,
        name_en=track.name_en,
        name_he=track.name_he,
        at=None if here is None else PositionModel.of(here),
        stages=rows,
    )


def _from_here(works: list[Work], ordinal: int) -> tuple[list[Work], int]:
    """The books from the one he is in onward, and how many of that book he has already done.

    Walked by ordinal rather than by title, so a code finished to the last halachah falls off the
    end and has nothing ahead of it -- which is the truth about it.

    Standing *at* halachah five means five are behind him, so five is what is done: an off-by-one
    here would overstate every distance on the screen.
    """
    consumed = 0
    for index, work in enumerate(works):
        if ordinal <= consumed + work.unit_count:
            return works[index:], ordinal - consumed
        consumed += work.unit_count
    return [], 0


async def _masechta_hebrew(session: AsyncSession) -> dict[str, str]:
    """Masechta name -> its Hebrew, from the catalog. Never assembled here."""
    rows = (await session.execute(select(Work.ref_title, Work.title_he).where(Work.corpus_id == "bavli"))).all()
    return {ref_title: title_he for ref_title, title_he in rows}
