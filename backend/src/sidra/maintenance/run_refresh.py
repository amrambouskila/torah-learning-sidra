"""Re-crawl Sefaria and write a new snapshot, as a job. The long one.

The snapshot is written only once the crawl has returned, so a job killed mid-crawl leaves no file
at all rather than half of one -- which is the property that lets the whole job system be a single
slot with no resume and no cleanup.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from sidra.catalog.crawl import crawl_catalog
from sidra.catalog.sefaria_client import SefariaClient
from sidra.catalog.snapshot import write_snapshot
from sidra.maintenance.job import Job


async def run_refresh(
    client: SefariaClient,
    sync_http: httpx.Client,
    snapshot_path: Path,
    include_links: bool,
    job: Job,
) -> str:
    result = await crawl_catalog(client, sync_http, include_links=include_links, on_progress=job.step)
    job.step("writing the snapshot")
    # Off the event loop: with links this is ~656 MB, and a blocked loop fails the container's
    # healthcheck, which with restart: unless-stopped would restart the backend mid-job.
    await asyncio.to_thread(write_snapshot, snapshot_path, result.payload)
    return f"{len(result.payload.works)} works, {result.unit_count} units, {result.edge_count} links"
