"""Rebuild the catalog from the committed snapshot, as a job.

Its dependencies are arguments rather than globals so it can be run against a small snapshot and a
test database, which is the only way the body of a background task gets tested at all.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sidra.catalog.snapshot import read_snapshot
from sidra.db.seed import seed_from_snapshot
from sidra.maintenance.job import Job
from sidra.maintenance.session_factory import SessionFactory


async def run_seed(factory: SessionFactory, snapshot_path: Path, job: Job) -> str:
    """One transaction, so a job killed halfway rolls back rather than half-seeding the catalog."""
    job.step("reading the snapshot")
    # Off the event loop: the snapshot is 19 MB and the healthcheck runs every ten seconds.
    payload = await asyncio.to_thread(read_snapshot, snapshot_path)
    job.step("writing the catalog")
    async with factory() as session, session.begin():
        counts = await seed_from_snapshot(session, payload)
    return f"{counts.works} works, {counts.units} stored units, {counts.aliases} aliases, {counts.links} links"
