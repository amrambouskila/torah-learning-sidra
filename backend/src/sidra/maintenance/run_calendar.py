"""Fetch a span of the Hebrew calendar, as a job.

The time is in the pauses: ``CRAWL_PAUSE_SECONDS`` between per-day calls means a four-hundred-day
span waits over two minutes before a single response is counted, which is exactly why this needed
to stop being a request and start being a job.
"""

from __future__ import annotations

from datetime import date, timedelta

import httpx

from sidra.calendar.calendar_source import fetch_calendar_range
from sidra.calendar.load_parsha_index import load_parsha_index
from sidra.calendar.store import store_calendar
from sidra.maintenance.job import Job
from sidra.maintenance.session_factory import SessionFactory


async def run_calendar(
    factory: SessionFactory,
    http: httpx.AsyncClient,
    start: date,
    days: int,
    job: Job,
    *,
    pause_seconds: float,
) -> str:
    """Fetch first, store in one transaction after, so a killed job leaves no partial span."""
    last = start + timedelta(days=days - 1)
    # The catalog names the parshiyos; the calendar only labels the weeks. Read the index before
    # crawling so a festival week is recognised as one rather than billed as a sidra.
    async with factory() as session:
        index = await load_parsha_index(session)
    fetched = await fetch_calendar_range(http, start, last, index, pause_seconds=pause_seconds, on_progress=job.step)
    job.step("storing the calendar")
    async with factory() as session, session.begin():
        stored = await store_calendar(session, fetched)
    return f"{stored} calendar days from {start} to {last}"
