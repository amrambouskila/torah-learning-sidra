from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.calendar.calendar_day import CalendarDay
from sidra.calendar.store import store_calendar
from sidra.db.models import Advance, Track
from sidra.ledger.seed_tracks import seed_tracks
from sidra.ledger.track_state import track_state
from sidra.ledger.tracks_file import parse_tracks_file
from tests.db.test_seed_tracks import AS_OF, HEBREW_AS_OF, TRACKS_YAML, _catalog

pytestmark = pytest.mark.integration


async def _calendar_through(session: AsyncSession, end: date) -> None:
    """A parsha week that turns over, so a combined week and a plain one are both exercised."""
    days = []
    current = AS_OF
    while current <= end:
        combined = current >= AS_OF + timedelta(days=7)
        days.append(
            CalendarDay(
                civil_date=current,
                hebrew_date=HEBREW_AS_OF,
                parsha_en=("Nitzavim", "Vayeilech") if combined else ("Ki Tavo",),
                parsha_he=("נצבים", "וילך") if combined else ("כי תבוא",),
                is_yom_tov=False,
            )
        )
        current += timedelta(days=1)
    await store_calendar(session, days)


async def _seeded(session: AsyncSession, through: date) -> None:
    await _catalog(session)
    await _calendar_through(session, through)
    await seed_tracks(session, parse_tracks_file(TRACKS_YAML))


async def _track(session: AsyncSession, name: str) -> Track:
    return (await session.execute(select(Track).where(Track.name_en == name))).scalar_one()


async def test_a_daily_track_owes_its_measured_debt_on_the_anchor_day(db_session: AsyncSession) -> None:
    await _seeded(db_session, AS_OF)
    state = await track_state(db_session, await _track(db_session, "Neviim"), AS_OF)
    assert state.ledger is not None
    assert state.ledger.debt == 3
    assert state.at is not None
    assert state.at.ref == "Jeremiah 44"
    assert state.scheduled_at is not None
    assert state.scheduled_at.ref == "Jeremiah 47"


async def test_the_debt_grows_by_one_a_day_when_nothing_is_learned(db_session: AsyncSession) -> None:
    await _seeded(db_session, AS_OF + timedelta(days=5))
    state = await track_state(db_session, await _track(db_session, "Neviim"), AS_OF + timedelta(days=5))
    assert state.ledger is not None
    assert state.ledger.debt == 8


async def test_the_next_unit_is_the_one_after_where_he_stands(db_session: AsyncSession) -> None:
    await _seeded(db_session, AS_OF)
    state = await track_state(db_session, await _track(db_session, "Neviim"), AS_OF)
    assert state.up_next is not None
    assert state.up_next.ref == "Jeremiah 45"


async def test_a_chavrusa_track_carries_staleness_and_no_debt(db_session: AsyncSession) -> None:
    await _seeded(db_session, AS_OF + timedelta(days=11))
    state = await track_state(db_session, await _track(db_session, "David Hadar — Brachot"), AS_OF + timedelta(days=11))
    assert state.ledger is None
    assert state.days_stale == 11
    assert state.at is not None
    assert state.at.ref == "Berakhot 13a"


async def test_the_chumash_owes_one_aliyah_a_day_and_two_in_a_combined_week(db_session: AsyncSession) -> None:
    await _seeded(db_session, AS_OF + timedelta(days=8))
    chumash = await _track(db_session, "Chumash")
    plain = await track_state(db_session, chumash, AS_OF + timedelta(days=6))
    combined = await track_state(db_session, chumash, AS_OF + timedelta(days=8))
    assert plain.ledger is not None and combined.ledger is not None
    # Seven plain days accrue seven; the next two are a combined week, so they accrue four more.
    assert combined.ledger.scheduled - plain.ledger.scheduled == 4


async def test_a_track_that_has_not_started_counts_down_without_touching_the_calendar(
    db_session: AsyncSession,
) -> None:
    """Its anchor is in October; asking for a span back to it would demand days nobody has stored."""
    await _seeded(db_session, AS_OF)
    state = await track_state(db_session, await _track(db_session, "Likutei Sichot"), AS_OF)
    assert state.ledger is not None
    assert state.ledger.debt == 0
    assert state.ledger.starts_in_days == 47
    assert state.at is None
    assert state.up_next is not None


async def test_an_unopened_track_stands_nowhere_but_has_a_next_unit(db_session: AsyncSession) -> None:
    await _seeded(db_session, AS_OF)
    state = await track_state(db_session, await _track(db_session, "Likutei Sichot"), AS_OF)
    assert state.actual_ordinal == 0
    assert state.at is None
    assert state.days_stale is None
    assert state.last_advanced_on is None
    assert not state.is_finished


async def test_a_finished_track_has_no_next_unit(db_session: AsyncSession) -> None:
    await _seeded(db_session, AS_OF)
    track = await _track(db_session, "David Hadar — Brachot")
    db_session.add(
        Advance(
            track_id=track.id,
            from_ordinal=125,
            to_ordinal=126,
            unit_count=1,
            occurred_at=datetime.combine(AS_OF, datetime.min.time(), tzinfo=UTC),
            hebrew_date=HEBREW_AS_OF,
            note=None,
        )
    )
    await db_session.flush()
    state = await track_state(db_session, track, AS_OF)
    assert state.is_finished
    assert state.up_next is None
    assert state.at is not None


async def test_a_gap_in_the_calendar_refuses_rather_than_under_accruing(db_session: AsyncSession) -> None:
    """A Chumash track that looks square while three aliyot behind is worse than one that errors."""
    await _seeded(db_session, AS_OF + timedelta(days=2))
    with pytest.raises(ValueError, match="run 'sidra-db calendar'"):
        await track_state(db_session, await _track(db_session, "Chumash"), AS_OF + timedelta(days=5))
