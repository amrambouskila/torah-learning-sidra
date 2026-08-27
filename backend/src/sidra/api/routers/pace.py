"""The Pace Explorer: what a full cycle would cost, at any rate or in any horizon.

Read-only and disconnected from the live plan on purpose. It answers "one amud a day is how many
years of Shas" without knowing or caring where Amram actually stands.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.deps import get_session
from sidra.api.models.pace_row import PaceRow
from sidra.constants import DAYS_PER_SOLAR_YEAR
from sidra.pace.counts import count_all, nouns_for
from sidra.pace.scopes_file import load_scopes

router = APIRouter(prefix="/api", tags=["pace"])

MAX_HORIZON_YEARS = 180.0
MAX_RATE_PER_DAY = 1000.0


@router.get("/pace", response_model=list[PaceRow])
async def get_pace(
    years: float = Query(default=1.0, gt=0, le=MAX_HORIZON_YEARS),
    per_day: float = Query(default=1.0, gt=0, le=MAX_RATE_PER_DAY),
    session: AsyncSession = Depends(get_session),
) -> list[PaceRow]:
    """Every row carries both answers, because they are two knobs rather than two modes."""
    counted = await count_all(session, load_scopes())
    if not counted:
        raise HTTPException(status_code=409, detail="the catalog holds no counted work; run 'sidra-db seed'")

    rows = []
    for row in counted:
        singular, plural = nouns_for(row.scope)
        rows.append(
            PaceRow(
                row_id=row.scope.id,
                scope_en=row.scope.scope_en,
                unit_singular=singular,
                unit_plural=plural,
                total=row.total,
                per_day_for_horizon=row.total / (DAYS_PER_SOLAR_YEAR * years),
                years_at_rate=row.total / (DAYS_PER_SOLAR_YEAR * per_day),
                note=row.scope.note,
            )
        )
    return rows
