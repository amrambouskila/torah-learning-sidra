"""An app wired to the rolled-back test session, so API tests never leak state.

``get_session`` is overridden rather than the engine swapped: the fixture's session is already
inside a transaction the harness rolls back, and letting the app open its own would commit.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.app import create_app
from sidra.api.deps import get_session, ledger_path, safety_copy_path, today
from sidra.calendar.calendar_day import CalendarDay
from sidra.calendar.store import store_calendar
from sidra.ledger.seed_tracks import seed_tracks
from sidra.ledger.tracks_file import parse_tracks_file
from tests.db.test_seed_tracks import AS_OF, HEBREW_AS_OF, TRACKS_YAML, _catalog

CALENDAR_DAYS = 20


async def seed_calendar(session: AsyncSession, days: int = CALENDAR_DAYS) -> None:
    """A run of plain weeks then a combined one, so both accrual rates are exercised."""
    span = []
    for offset in range(days):
        combined = offset >= 7
        span.append(
            CalendarDay(
                civil_date=AS_OF + timedelta(days=offset),
                hebrew_date=HEBREW_AS_OF,
                parsha_en=("Nitzavim", "Vayeilech") if combined else ("Ki Tavo",),
                parsha_he=("נצבים", "וילך") if combined else ("כי תבוא",),
                is_yom_tov=False,
            )
        )
    await store_calendar(session, span)


@pytest.fixture
async def seeded_session(db_session: AsyncSession) -> AsyncSession:
    """A miniature catalog, a calendar and the four-track sidra from the seeder tests."""
    await _catalog(db_session)
    await seed_calendar(db_session)
    await seed_tracks(db_session, parse_tracks_file(TRACKS_YAML))
    return db_session


@pytest.fixture
def app(seeded_session: AsyncSession, tmp_path: Path) -> FastAPI:
    application = create_app()

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield seeded_session

    application.dependency_overrides[get_session] = session_override
    application.dependency_overrides[today] = lambda: AS_OF
    # A correction writes the ledger to disk before deleting anything; without this every test
    # that makes one would write into the project's own data directory.
    application.dependency_overrides[safety_copy_path] = lambda: tmp_path / "ledger.before-correction.json"
    # Likewise the export button, or pressing it in a test would overwrite the committed ledger.
    application.dependency_overrides[ledger_path] = lambda: tmp_path / "ledger.json"
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://sidra.test") as http:
        yield http


def on(offset: int) -> dict[str, str]:
    """Query params pinning a request to a day relative to the seed's ``as_of``."""
    return {"on": (AS_OF + timedelta(days=offset)).isoformat()}


AS_OF_DATE: date = AS_OF

__all__ = ["AS_OF", "AS_OF_DATE", "HEBREW_AS_OF", "on", "seed_calendar"]
