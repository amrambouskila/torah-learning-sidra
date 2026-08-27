"""The commands that used to need a terminal.

Six of the nine ``sidra-db`` verbs, and the three that are missing are missing on purpose:
``init`` the launcher already runs on boot, and ``seed-tracks`` and ``import`` both call
``clear_ledger`` -- putting either behind a button in the app where he taps *Advance* every morning
would leave "erase every advance you have recorded" two clicks from the daily gesture. The one
narrow exception is ``/restore``, which reads the correction safety copy and no other file.

Nothing here reimplements a command. The CLI verbs are already thin wrappers over
``export_ledger``, ``check_catalog``, ``seed_from_snapshot``, ``crawl_catalog`` and
``fetch_calendar_range``; these routes are a second caller of the same functions.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.deps import get_session, ledger_path, safety_copy_path
from sidra.api.models.calendar_request import CalendarRequest
from sidra.api.models.export_result import ExportResult
from sidra.api.models.job_view import JobView
from sidra.api.models.maintenance_status import MaintenanceStatus
from sidra.api.models.refresh_request import RefreshRequest
from sidra.api.models.restore_request import RestoreRequest
from sidra.api.models.verify_result import VerifyResult
from sidra.catalog.sefaria_client import SefariaClient
from sidra.catalog.snapshot import DEFAULT_SNAPSHOT_PATH
from sidra.config import get_settings
from sidra.db.models import Advance, LearnableUnit, Track, Work
from sidra.db.seed import catalog_is_empty
from sidra.expected_counts import check_catalog, load_expected_counts
from sidra.ledger.ledger_file import read_ledger, write_ledger
from sidra.ledger.seed_tracks import ledger_is_empty
from sidra.ledger.transfer import export_ledger, import_ledger
from sidra.maintenance.job import Job
from sidra.maintenance.job_registry import JobRegistry
from sidra.maintenance.run_calendar import run_calendar
from sidra.maintenance.run_refresh import run_refresh
from sidra.maintenance.run_seed import run_seed
from sidra.maintenance.session_factory import SessionFactory

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])

CRAWL_PAUSE_SECONDS = 0.4
"""Sefaria answers an unthrottled four-hundred-day crawl with 429 partway through."""


def _registry(request: Request) -> JobRegistry:
    """The one slot, created on first use and living as long as the process."""
    existing = getattr(request.app.state, "jobs", None)
    if existing is None:
        existing = JobRegistry()
        request.app.state.jobs = existing
    return existing


def _written_at(path: Path) -> datetime | None:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC) if path.exists() else None


@router.get("", response_model=MaintenanceStatus)
async def get_status(
    session: AsyncSession = Depends(get_session),
    ledger: Path = Depends(ledger_path),
    safety_copy: Path = Depends(safety_copy_path),
) -> MaintenanceStatus:
    """What the screen shows before he presses anything."""
    return MaintenanceStatus(
        catalog_seeded=not await catalog_is_empty(session),
        ledger_seeded=not await ledger_is_empty(session),
        works=int(await session.scalar(select(func.count()).select_from(Work)) or 0),
        stored_units=int(await session.scalar(select(func.count()).select_from(LearnableUnit)) or 0),
        tracks=int(await session.scalar(select(func.count()).select_from(Track)) or 0),
        advances=int(await session.scalar(select(func.count()).select_from(Advance)) or 0),
        ledger_exported_at=_written_at(ledger),
        safety_copy_at=_written_at(safety_copy),
    )


@router.get("/job", response_model=JobView | None)
async def get_job(request: Request) -> JobView | None:
    """The running job, or the last one to finish, or null if none has run since the app started."""
    job = _registry(request).current
    return None if job is None else JobView.of(job)


@router.post("/export", response_model=ExportResult)
async def run_export(
    session: AsyncSession = Depends(get_session),
    ledger: Path = Depends(ledger_path),
) -> ExportResult:
    """Write the ledger to ``data/ledger.json``. Fast enough to answer in the request."""
    document = await export_ledger(session)
    # Off the loop: the healthcheck runs every ten seconds and a large write would block it.
    await asyncio.to_thread(write_ledger, ledger, document)
    return ExportResult(
        path=str(ledger),
        tracks=len(document.tracks),
        advances=len(document.advances),
        chavrusas=len(document.chavrusas),
        tags=len(document.tags),
        calendar_days=len(document.calendar),
    )


@router.post("/verify", response_model=VerifyResult)
async def run_verify(session: AsyncSession = Depends(get_session)) -> VerifyResult:
    """Check the seeded catalog against the expected counts. Reads only."""
    failures = await check_catalog(session, load_expected_counts())
    return VerifyResult(matches=not failures, failures=list(failures))


@router.post("/restore", response_model=ExportResult)
async def run_restore(
    body: RestoreRequest,
    session: AsyncSession = Depends(get_session),
    safety_copy: Path = Depends(safety_copy_path),
) -> ExportResult:
    """Put the ledger back to the copy a correction wrote before it deleted anything.

    The only button in the app that can destroy learning, and it exists to undo the only other
    thing that can. It reads one known file: there is no path in the request, so it cannot be
    talked into replacing the ledger from anywhere else.
    """
    if not safety_copy.exists():
        # read_ledger's own message tells him to run an export on the old machine, which is the
        # right advice for a move between machines and the wrong advice here.
        raise HTTPException(
            status_code=409,
            detail="no correction has written a safety copy yet, so there is nothing to go back to",
        )
    try:
        document = await asyncio.to_thread(read_ledger, safety_copy)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    counts = await import_ledger(session, document)
    return ExportResult(
        path=str(safety_copy),
        tracks=counts.tracks,
        advances=counts.advances,
        chavrusas=counts.chavrusas,
        tags=counts.tags,
        calendar_days=counts.calendar_days,
    )


async def _start(request: Request, kind: str, work: Callable[[Job], Awaitable[str]]) -> JobView:
    """Claim the slot and run the work in the background, answering with the job at once."""
    registry = _registry(request)
    if registry.is_busy:
        current = registry.current
        raise HTTPException(
            status_code=409,
            detail=f"a {current.kind if current else '?'} job is already running; wait for it to finish",
        )
    job = registry.start(kind)

    async def run() -> None:
        try:
            registry.finish(job, await work(job))
        except Exception as error:  # noqa: BLE001 - a job must record why it stopped, not vanish
            registry.abandon(job, f"{type(error).__name__}: {error}")

    request.app.state.job_task = asyncio.create_task(run())
    return JobView.of(job)


def _factory(request: Request) -> SessionFactory:
    """A background job outlives the request, so it cannot borrow the request's session."""
    factory: SessionFactory = request.app.state.session_factory
    return factory


@router.post("/seed", response_model=JobView, status_code=202)
async def start_seed(request: Request) -> JobView:
    """Rebuild the catalog from the committed snapshot. Offline, deterministic, ledger untouched."""
    return await _start(request, "seed", lambda job: run_seed(_factory(request), DEFAULT_SNAPSHOT_PATH, job))


@router.post("/calendar", response_model=JobView, status_code=202)
async def start_calendar(request: Request, body: CalendarRequest) -> JobView:
    """Fetch a span of the Hebrew calendar and store it."""

    async def work(job: Job) -> str:
        timeout = get_settings().http_timeout_seconds * 10
        async with httpx.AsyncClient(timeout=timeout) as http:
            return await run_calendar(
                _factory(request), http, body.start, body.days, job, pause_seconds=CRAWL_PAUSE_SECONDS
            )

    return await _start(request, "calendar", work)


@router.post("/refresh", response_model=JobView, status_code=202)
async def start_refresh(request: Request, body: RefreshRequest) -> JobView:
    """Re-crawl Sefaria and write a new snapshot. The long one."""

    async def work(job: Job) -> str:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds * 10) as async_http:
            client = SefariaClient(async_http, settings.sefaria_base_url)
            with httpx.Client(timeout=300.0) as sync_http:
                return await run_refresh(client, sync_http, DEFAULT_SNAPSHOT_PATH, body.include_links, job)

    return await _start(request, "refresh", work)
