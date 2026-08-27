"""Dated projections, and the Pace Explorer's yearly-cycle rate.

With a fixed rate and a complete catalog, a projection is arithmetic rather than inference:

    units_remaining  = total - actual
    projected_finish = today + (units_remaining + debt) / rate_per_day

Every day of debt slides the date by exactly one day, which is the point of showing it.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.deps import get_session, today
from sidra.api.models.roadmap_row import RoadmapRow
from sidra.api.track_rows import active_tracks
from sidra.constants import DAYS_PER_SOLAR_YEAR
from sidra.db.models import Work
from sidra.ledger.effective_anchor import effective_anchor
from sidra.ledger.period import Period
from sidra.ledger.track_state import track_state

router = APIRouter(prefix="/api", tags=["roadmap"])

DAYS_PER_WEEK = 7

CORPUS_NAMES = {
    "bavli": "Talmud Bavli",
    "mishnah": "Mishnah",
    "mishneh_torah": "Mishneh Torah",
    "shulchan_aruch": "Shulchan Aruch",
    "neviim": "Neviim",
    "ketuvim": "Ketuvim",
    "torah": "Torah",
}
"""Bodies a single-work track can sit inside. A track over the whole corpus already projects it."""


async def _wider_body(session: AsyncSession, work_ref_title: str) -> Work | None:
    """The corpus a track's current work belongs to, when the track is only part of it."""
    work = (await session.execute(select(Work).where(Work.ref_title == work_ref_title))).scalar_one_or_none()
    if work is None or work.corpus_id not in CORPUS_NAMES:
        return None
    return work


async def _corpus_total(session: AsyncSession, work: Work) -> int | None:
    """Every unit in the corpus at the same granularity, when the corpus holds more than one work.

    Two guards, both load-bearing. Granularity, because the Torah corpus holds perakim and aliyot
    at once and summing it whole would measure 378 aliyot against 619 of nothing in particular.
    And more-than-one, because a track over the corpus's only work of its kind -- the Chumash over
    Parashat HaShavua -- has no wider body to be part of.
    """
    row = (
        await session.execute(
            select(func.count(), func.sum(Work.unit_count)).where(
                Work.corpus_id == work.corpus_id, Work.granularity == work.granularity
            )
        )
    ).one()
    works, units = row
    return int(units or 0) if works > 1 else None


def rate_per_day(rate: int, period: Period) -> float:
    """A weekly rate spread across the week, so every track projects on one clock."""
    return rate if period is Period.DAY else rate / DAYS_PER_WEEK


@router.get("/roadmap", response_model=list[RoadmapRow])
async def get_roadmap(
    on: date | None = None,
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> list[RoadmapRow]:
    day = on or default_day
    rows = []
    try:
        for track in await active_tracks(session):
            state = await track_state(session, track, day)
            remaining = max(0, state.total - state.actual_ordinal)
            debt = 0 if state.ledger is None else max(0, state.ledger.debt)
            per_day = rate_per_day(track.rate, track.period)

            here = state.at or state.up_next
            work_title = None if here is None else here.work_ref_title
            body = await _wider_body(session, work_title or "")
            corpus_total = None
            if body is not None:
                corpus_total = await _corpus_total(session, body)
                if corpus_total is None or corpus_total <= state.total:
                    body, corpus_total = None, None
            rows.append(
                RoadmapRow(
                    track_id=track.id,
                    name_en=track.name_en,
                    name_he=track.name_he,
                    work_ref_title=work_title,
                    corpus_en=None if body is None else CORPUS_NAMES[body.corpus_id],
                    corpus_total=corpus_total,
                    corpus_years=None
                    if corpus_total is None or per_day == 0
                    else corpus_total / per_day / DAYS_PER_SOLAR_YEAR,
                    total=state.total,
                    actual_ordinal=state.actual_ordinal,
                    units_remaining=remaining,
                    rate_per_day=per_day,
                    debt=debt,
                    projected_finish=None
                    if per_day == 0
                    # A track that has not begun finishes from its start date, not from today.
                    else max(day, effective_anchor(track.anchor_date, track.starts_on))
                    + timedelta(days=round(remaining / per_day)),
                    yearly_cycle_rate=state.total / DAYS_PER_SOLAR_YEAR,
                )
            )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return rows
