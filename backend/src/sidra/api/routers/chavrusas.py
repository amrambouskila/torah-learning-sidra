"""Chavrusas, staleness-sorted, with their session history.

A chavrusa track carries no debt -- it moves when they meet -- so the only question worth asking is
how long it has been. The list is ordered by that, longest first.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.deps import get_session, today
from sidra.api.models.chavrusa_row import ChavrusaRow
from sidra.api.models.session_row import SessionRow
from sidra.api.track_rows import build_rows
from sidra.db.models import Advance, Chavrusa, Track

router = APIRouter(prefix="/api", tags=["chavrusas"])

NEVER_MET_SORT_KEY = float("-inf")
"""A chavrusa they have never sat with sorts above any measured staleness, however long."""


@router.get("/chavrusas", response_model=list[ChavrusaRow])
async def list_chavrusas(
    on: date | None = None,
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> list[ChavrusaRow]:
    day = on or default_day
    people = list((await session.execute(select(Chavrusa).order_by(Chavrusa.name))).scalars().all())

    rows = []
    try:
        for person in people:
            tracks = list(
                (await session.execute(select(Track).where(Track.chavrusa_id == person.id).order_by(Track.name_en)))
                .scalars()
                .all()
            )
            track_rows = await build_rows(session, tracks, day)
            advance_rows = await session.execute(
                select(Advance)
                .where(Advance.track_id.in_([track.id for track in tracks]))
                # Two sessions on one day tie on the timestamp, so the further ordinal is the
                # later one -- otherwise the newest session can sort beneath the one it followed.
                .order_by(Advance.occurred_at.desc(), Advance.to_ordinal.desc())
            )
            stale = [row.days_stale for row in track_rows if row.days_stale is not None]
            rows.append(
                ChavrusaRow(
                    id=person.id,
                    name=person.name,
                    notes=person.notes,
                    days_stale=min(stale) if stale else None,
                    tracks=track_rows,
                    sessions=[
                        SessionRow(
                            occurred_on=advance.occurred_at.date(),
                            hebrew_date=advance.hebrew_date,
                            from_ordinal=advance.from_ordinal,
                            to_ordinal=advance.to_ordinal,
                            unit_count=advance.unit_count,
                            note=advance.note,
                        )
                        for advance in advance_rows.scalars().all()
                    ],
                )
            )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    rows.sort(key=lambda row: (NEVER_MET_SORT_KEY if row.days_stale is None else -row.days_stale, row.name))
    return rows
