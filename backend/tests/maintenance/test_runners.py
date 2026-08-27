"""The three long jobs, run for real against stubbed upstreams and the test database.

Nothing here is mocked in the sense the rules forbid: the database is the real compose Postgres and
the catalog logic is the real crawl. Only the two upstreams are stubbed, with the same
``httpx.MockTransport`` the crawl and calendar suites already use — a test that pulls 656 MB from
Sefaria is not a test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.sefaria_client import SefariaClient
from sidra.catalog.snapshot import read_snapshot
from sidra.maintenance.job import Job
from sidra.maintenance.run_calendar import run_calendar
from sidra.maintenance.run_refresh import run_refresh
from sidra.maintenance.run_seed import run_seed
from tests.calendar.test_calendar_source import HEBCAL_CONVERTER, HEBCAL_EVENTS, SEFARIA_SINGLE, hdates
from tests.db.test_load_parsha_index import PARSHIYOS_IN_A_CYCLE, _seed_parshiyos
from tests.maintenance.savepoint_factory import SavepointFactory
from tests.test_crawl_orchestration import _handler

pytestmark = pytest.mark.integration


def _job(kind: str) -> Job:
    return Job(kind=kind, started_at=datetime.now(UTC))


class RecordingJob(Job):
    """A job that remembers every tick. ``Job`` has slots, so this is a subclass rather than a patch."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind=kind, started_at=datetime.now(UTC))
        self.seen: list[tuple[str, int, int]] = []

    def step(self, phase: str, done: int = 0, total: int = 0) -> None:
        self.seen.append((phase, done, total))
        super().step(phase, done, total)


def _client(handler: object = _handler) -> SefariaClient:
    return SefariaClient(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),  # type: ignore[arg-type]
        "https://www.sefaria.org/api",
        backoff_seconds=0.0,
    )


# --- refresh: crawl, then write ------------------------------------------------------------------


async def test_refresh_writes_a_snapshot_the_seed_can_read_back(tmp_path: Path) -> None:
    """The two halves of the loop meet here: what the crawl writes, the rebuild reads."""
    out = tmp_path / "p1.jsonl"
    job = _job("refresh")

    detail = await run_refresh(_client(), httpx.Client(transport=httpx.MockTransport(_handler)), out, False, job)

    assert out.exists()
    assert "works" in detail and "units" in detail
    assert read_snapshot(out).works
    assert job.phase == "writing the snapshot"


async def test_refresh_writes_nothing_when_the_crawl_fails(tmp_path: Path) -> None:
    """The property the whole one-slot job design rests on: a killed crawl leaves no half file."""
    out = tmp_path / "p1.jsonl"

    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _client(broken)
    with pytest.raises(Exception, match=r".*"):
        await run_refresh(client, httpx.Client(transport=httpx.MockTransport(broken)), out, False, _job("refresh"))

    assert not out.exists()


# --- seed: read, then write, in one transaction --------------------------------------------------


async def test_seed_rebuilds_the_catalog_from_a_snapshot(db_session: AsyncSession, tmp_path: Path) -> None:
    snapshot = tmp_path / "p1.jsonl"
    crawled = _job("refresh")
    await run_refresh(_client(), httpx.Client(transport=httpx.MockTransport(_handler)), snapshot, False, crawled)
    job = _job("seed")

    detail = await run_seed(SavepointFactory(db_session), snapshot, job)

    assert "works" in detail
    assert job.phase == "writing the catalog"


async def test_seed_reports_reading_before_writing(db_session: AsyncSession, tmp_path: Path) -> None:
    """One transaction with no natural tick, so it reports phases rather than a count."""
    snapshot = tmp_path / "p1.jsonl"
    await run_refresh(
        _client(), httpx.Client(transport=httpx.MockTransport(_handler)), snapshot, False, _job("refresh")
    )
    job = RecordingJob("seed")

    await run_seed(SavepointFactory(db_session), snapshot, job)

    assert [phase for phase, _, _ in job.seen] == ["reading the snapshot", "writing the catalog"]


# --- calendar: fetch, then store -----------------------------------------------------------------


def _calendar_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "sefaria" in url:
        return httpx.Response(200, json=SEFARIA_SINGLE)
    if "converter" in url:
        return httpx.Response(200, json=hdates(**{f"2026-10-0{n}": HEBCAL_CONVERTER for n in (2, 3, 4)}))
    return httpx.Response(200, json=HEBCAL_EVENTS)


async def test_calendar_fetches_a_span_and_stores_it(db_session: AsyncSession) -> None:
    # The calendar only labels the weeks; the catalog names the parshiyos, so it must be there.
    await _seed_parshiyos(db_session, count=PARSHIYOS_IN_A_CYCLE)
    job = _job("calendar")
    async with httpx.AsyncClient(transport=httpx.MockTransport(_calendar_handler)) as http:
        detail = await run_calendar(SavepointFactory(db_session), http, date(2026, 10, 2), 3, job, pause_seconds=0.0)

    assert "3 calendar days" in detail
    assert job.phase == "storing the calendar"


async def test_calendar_ticks_once_a_day_because_that_is_where_the_time_goes(
    db_session: AsyncSession,
) -> None:
    """At the real pause a four-hundred-day span waits two minutes before a single response."""
    await _seed_parshiyos(db_session, count=PARSHIYOS_IN_A_CYCLE)
    job = RecordingJob("calendar")

    async with httpx.AsyncClient(transport=httpx.MockTransport(_calendar_handler)) as http:
        await run_calendar(SavepointFactory(db_session), http, date(2026, 10, 2), 3, job, pause_seconds=0.0)

    fetches = [phase for phase, _, _ in job.seen if phase.startswith("fetching ")]
    assert fetches == ["fetching 2026-10-02", "fetching 2026-10-03", "fetching 2026-10-04"]
    assert all(total == 3 for phase, _, total in job.seen if phase.startswith("fetching "))
