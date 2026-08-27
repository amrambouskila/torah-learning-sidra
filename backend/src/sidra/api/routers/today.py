"""The Today view: every active track, grouped by the three fixed categories."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.deps import get_session, today
from sidra.api.models.today_response import TodayResponse
from sidra.api.track_rows import active_tracks, build_rows
from sidra.calendar.store import calendar_day
from sidra.ledger.category import Category

router = APIRouter(prefix="/api", tags=["today"])


@router.get("/today", response_model=TodayResponse)
async def get_today(
    on: date | None = None,
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> TodayResponse:
    """Every active track with its position, debt and staleness. Computes; stores nothing."""
    day = on or default_day
    try:
        calendar = await calendar_day(session, day)
        rows = await build_rows(session, await active_tracks(session), day)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return TodayResponse(
        civil_date=calendar.civil_date,
        hebrew_date=calendar.hebrew_date,
        parsha_en=list(calendar.parsha_en),
        parsha_he=list(calendar.parsha_he),
        is_yom_tov=calendar.is_yom_tov,
        daily=[row for row in rows if row.category is Category.DAILY],
        shabbat=[row for row in rows if row.category is Category.SHABBAT],
        chavrusa=[row for row in rows if row.category is Category.CHAVRUSA],
    )
