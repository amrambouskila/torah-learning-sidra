"""The ``sidra-db`` command line.

Nine verbs, and the distinction between two of them is the important part:

``init``          creates the schema. Safe to re-run; it only adds what is missing.
``seed``          rebuilds the catalog from the committed snapshot. Offline, deterministic, seconds.
``refresh``       re-crawls Sefaria and writes a NEW snapshot. Deliberate; never on boot.
``calendar``      fetches a span of the Hebrew calendar. Also deliberate; also never on boot.
``seed-tracks``   writes Amram's sidra from ``data/tracks.yaml``, resolving every position against
                  the catalog. Needs the catalog and the calendar to be there first.
``export``        writes the ledger to ``data/ledger.json``. Run it before copying the project to
                  another machine: the catalog rebuilds from the snapshot, the ledger cannot.
``import``        reads that file back, replacing whatever ledger is there.

A launcher that ran ``refresh`` at startup would pull 656 MB before the app came up.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path

import httpx
import typer

from sidra.calendar.calendar_source import fetch_calendar_range
from sidra.calendar.load_parsha_index import load_parsha_index
from sidra.calendar.store import store_calendar
from sidra.catalog.crawl import crawl_catalog
from sidra.catalog.sefaria_client import SefariaClient
from sidra.catalog.snapshot import DEFAULT_SNAPSHOT_PATH, read_snapshot, write_snapshot
from sidra.config import get_settings
from sidra.db.base import Base
from sidra.db.engine import create_engine, create_session_factory
from sidra.db.seed import catalog_is_empty, seed_from_snapshot
from sidra.expected_counts import check_catalog, load_expected_counts
from sidra.ledger.ledger_file import LEDGER_PATH, read_ledger, write_ledger
from sidra.ledger.seed_tracks import ledger_is_empty, seed_tracks
from sidra.ledger.tracks_file import load_tracks_file
from sidra.ledger.transfer import export_ledger, import_ledger

DEFAULT_SNAPSHOT = DEFAULT_SNAPSHOT_PATH

app = typer.Typer(add_completion=False, help="Torah Learning Sidra catalog database tool.")


def _session_factory() -> tuple[object, object]:
    engine = create_engine(get_settings().database_url)
    return engine, create_session_factory(engine)


@app.command()
def init() -> None:
    """Create the schema. Safe to re-run: it adds what is missing and touches nothing else."""

    async def run() -> None:
        engine = create_engine(get_settings().database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()
        typer.echo(f"schema ready: {len(Base.metadata.tables)} tables")

    asyncio.run(run())


@app.command()
def seed(snapshot: Path = typer.Option(DEFAULT_SNAPSHOT, help="Snapshot to rebuild from.")) -> None:
    """Rebuild the catalog from a committed snapshot. Offline and deterministic."""

    async def run() -> None:
        payload = read_snapshot(snapshot)
        engine, factory = _session_factory()
        async with factory() as session, session.begin():  # type: ignore[operator]
            counts = await seed_from_snapshot(session, payload)
        await engine.dispose()  # type: ignore[attr-defined]
        typer.echo(
            f"seeded {counts.works} works, {counts.units} stored units, {counts.aliases} aliases, {counts.links} links"
        )

    asyncio.run(run())


@app.command()
def refresh(
    out: Path = typer.Option(DEFAULT_SNAPSHOT, help="Where to write the new snapshot."),
    links: bool = typer.Option(True, help="Include the Ein Mishpat export (~656 MB)."),
) -> None:
    """Re-crawl Sefaria and write a new snapshot. Deliberate; never run on boot."""

    async def run() -> None:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds * 10) as async_http:
            client = SefariaClient(async_http, settings.sefaria_base_url)
            with httpx.Client(timeout=300.0) as sync_http:
                result = await crawl_catalog(client, sync_http, include_links=links)
        write_snapshot(out, result.payload)
        typer.echo(
            f"wrote {out}: {len(result.payload.works)} works, {result.unit_count} units, {result.edge_count} links"
        )

    asyncio.run(run())


@app.command()
def verify() -> None:
    """Check the seeded catalog against the expected counts. Exits non-zero on mismatch."""

    async def run() -> None:
        engine, factory = _session_factory()
        async with factory() as session:  # type: ignore[operator]
            failures = await check_catalog(session, load_expected_counts())
        await engine.dispose()  # type: ignore[attr-defined]
        for failure in failures:
            typer.echo(f"MISMATCH  {failure}", err=True)
        if failures:
            raise typer.Exit(code=1)
        typer.echo("catalog matches every expected count")

    asyncio.run(run())


CRAWL_PAUSE_SECONDS = 0.4
"""Sefaria answers an unthrottled four-hundred-day crawl with 429 partway through."""


@app.command()
def calendar(
    start: str = typer.Option(..., help="First civil date, ISO format."),
    days: int = typer.Option(400, help="How many days to fetch. A yearly cycle needs at least 380."),
) -> None:
    """Fetch a span of the Hebrew calendar and store it. Deliberate; never run on boot."""

    async def run() -> None:
        first = date.fromisoformat(start)
        last = first + timedelta(days=days - 1)
        settings = get_settings()
        engine, factory = _session_factory()
        # The catalog names the parshiyos; the calendar only labels the weeks. Read the index
        # before crawling so a festival week is recognised as one rather than billed as a sidra.
        async with factory() as session:  # type: ignore[operator]
            index = await load_parsha_index(session)
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds * 10) as http:
            fetched = await fetch_calendar_range(http, first, last, index, pause_seconds=CRAWL_PAUSE_SECONDS)
        async with factory() as session, session.begin():  # type: ignore[operator]
            stored = await store_calendar(session, fetched)
        await engine.dispose()  # type: ignore[attr-defined]
        typer.echo(f"stored {stored} calendar days from {first} to {last}")

    asyncio.run(run())


@app.command("seed-tracks")
def seed_tracks_command() -> None:
    """Write Amram's sidra from ``data/tracks.yaml``, resolving every position against the catalog."""

    async def run() -> None:
        spec_file = load_tracks_file()
        engine, factory = _session_factory()
        async with factory() as session, session.begin():  # type: ignore[operator]
            counts = await seed_tracks(session, spec_file)
        await engine.dispose()  # type: ignore[attr-defined]
        typer.echo(
            f"seeded {counts.tracks} tracks, {counts.chavrusas} chavrusas, {counts.tags} tags, "
            f"{counts.advances} opening advances, {counts.tagged} tag links"
        )

    asyncio.run(run())


@app.command("export")
def export_command(out: Path = typer.Option(LEDGER_PATH, help="Where to write the ledger.")) -> None:
    """Write the ledger to a file. Run this before copying the project to another machine.

    The catalog rebuilds from the committed snapshot; the ledger cannot, because every advance
    exists nowhere but this database -- and that database lives in a Docker volume, not in the
    project folder.
    """

    async def run() -> None:
        engine, factory = _session_factory()
        async with factory() as session:  # type: ignore[operator]
            document = await export_ledger(session)
        await engine.dispose()  # type: ignore[attr-defined]
        write_ledger(out, document)
        typer.echo(
            f"wrote {out}: {len(document.tracks)} tracks, {len(document.advances)} advances, "
            f"{len(document.chavrusas)} chavrusas, {len(document.tags)} tags, "
            f"{len(document.calendar)} calendar days"
        )

    asyncio.run(run())


@app.command("import")
def import_command(
    source: Path = typer.Option(LEDGER_PATH, help="The ledger export to read."),
) -> None:
    """Replace the ledger from a file. Leaves the catalog alone."""

    async def run() -> None:
        document = read_ledger(source)
        engine, factory = _session_factory()
        async with factory() as session, session.begin():  # type: ignore[operator]
            counts = await import_ledger(session, document)
        await engine.dispose()  # type: ignore[attr-defined]
        typer.echo(
            f"imported {counts.tracks} tracks, {counts.advances} advances, {counts.chavrusas} chavrusas, "
            f"{counts.tags} tags, {counts.calendar_days} calendar days"
        )

    asyncio.run(run())


@app.command()
def status() -> None:
    """Report whether the catalog and the ledger hold anything. The launcher reads this."""

    async def run() -> None:
        engine, factory = _session_factory()
        async with factory() as session:  # type: ignore[operator]
            catalog = "empty" if await catalog_is_empty(session) else "seeded"
            ledger = "empty" if await ledger_is_empty(session) else "seeded"
        await engine.dispose()  # type: ignore[attr-defined]
        typer.echo(f"catalog {catalog}, ledger {ledger}")

    asyncio.run(run())


if __name__ == "__main__":  # pragma: no cover
    app()
