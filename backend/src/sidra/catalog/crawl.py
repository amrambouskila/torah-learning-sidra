"""Run every ingester once, under one snapshot.

This is the piece that composes the catalog. Without it the ingesters are nine functions nobody
calls: an earlier draft of the plan had exactly that, and neither the CLI nor the acceptance suite
could work because nothing produced a snapshot.

Order matters in one place: the parsha-weekly works borrow the 54-parsha spine, so the parshiyos
must be ingested before them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import httpx

from sidra.alignment.ein_mishpat import EinMishpatEdge, iter_all_ein_mishpat
from sidra.alignment.tur_bridge import bridge_via_tur
from sidra.catalog.corpora import ORCHOT_TZADIKIM, corpora, single_works
from sidra.catalog.granularity import Granularity
from sidra.catalog.ingest import ingest_corpus
from sidra.catalog.ingest_aliases import AliasRow, local_alias_rows, sefaria_aliases
from sidra.catalog.ingest_named import NamedWorkSpec, ingest_named_work
from sidra.catalog.ingest_parsha import ingest_parshiyos
from sidra.catalog.ingest_parsha_works import build_parsha_work_drafts
from sidra.catalog.sefaria_client import SefariaClient
from sidra.catalog.sefaria_error import SefariaError
from sidra.catalog.snapshot import FORMAT_VERSION, SnapshotPayload
from sidra.catalog.stored_unit import StoredUnitRow
from sidra.catalog.work_draft import WorkDraft
from sidra.maintenance.progress import OnProgress

PARSHA_WORK_REF_TITLE = "Parashat HaShavua"


@dataclass(frozen=True, slots=True)
class CrawlResult:
    payload: SnapshotPayload
    unit_count: int
    edge_count: int


def renumber_corpus_seq(drafts: Sequence[WorkDraft]) -> list[WorkDraft]:
    """Assign a contiguous ``corpus_seq`` per corpus, in the order the drafts arrived.

    Several specs share a corpus_id -- four mussar works, three chassidus -- and each spec numbers
    from 1, so without this the unique constraint on (corpus_id, corpus_seq) rejects the second.
    """
    counters: dict[str, int] = {}
    renumbered: list[WorkDraft] = []
    for draft in drafts:
        counters[draft.corpus_id] = counters.get(draft.corpus_id, 0) + 1
        renumbered.append(replace(draft, corpus_seq=counters[draft.corpus_id]))
    return renumbered


ALIAS_CONCURRENCY = 8
"""Alias harvesting is one raw-index call per work, and there are roughly 250 works.

Sequentially that dominates the whole crawl. Eight at a time keeps it to well under a minute
without hammering an API that publishes no rate limit and therefore deserves restraint.
"""


async def _harvest_aliases(client: SefariaClient, drafts: Sequence[WorkDraft]) -> list[AliasRow]:
    """Collect Sefaria's own spellings, then Amram's.

    A work whose raw index cannot be fetched contributes no Sefaria aliases rather than failing the
    crawl: the local aliases are the ones that matter for search, and they are validated strictly.
    """
    fetchable = [d for d in drafts if d.index_title is not None and d.source == "sefaria"]
    semaphore = asyncio.Semaphore(ALIAS_CONCURRENCY)

    async def harvest(draft: WorkDraft) -> list[AliasRow]:
        async with semaphore:
            try:
                payload = await client.raw_index(str(draft.index_title))
            except SefariaError:
                return []
        return sefaria_aliases(draft.ref_title, payload)

    harvested = await asyncio.gather(*(harvest(draft) for draft in fetchable))
    rows = [row for batch in harvested for row in batch]
    rows.extend(local_alias_rows(draft.ref_title for draft in drafts))
    return rows


async def crawl_catalog(
    client: SefariaClient,
    http: httpx.Client,
    *,
    include_links: bool = True,
    on_progress: OnProgress | None = None,
) -> CrawlResult:
    """Ingest everything and return one snapshot payload.

    ``include_links`` exists so a structural crawl can skip the 656 MB link export; the catalog is
    complete either way, only the topic map is absent.

    ``on_progress`` is optional and defaults to nobody watching, which is what the CLI wants. The
    Maintenance screen passes one so a ninety-second crawl is not a spinner with nothing behind it.
    """
    drafts: list[WorkDraft] = []
    units: list[tuple[str, StoredUnitRow]] = []

    specs = [*corpora(), *single_works()]
    steps = len(specs) + 3
    for index, spec in enumerate(specs, start=1):
        if on_progress is not None:
            on_progress(f"crawling {spec.corpus_id}", index - 1, steps)
        drafts.extend(await ingest_corpus(client, spec))

    drafts.append(
        await ingest_named_work(
            client,
            NamedWorkSpec(
                corpus_id="mussar",
                corpus_seq=0,
                ref_title=ORCHOT_TZADIKIM,
                alt_key="Gate",
                granularity=Granularity.GATE,
            ),
        )
    )

    if on_progress is not None:
        on_progress("crawling the parsha cycle", len(specs) + 1, steps)
    parsha_draft, parsha_rows = await ingest_parshiyos(client)
    drafts.append(parsha_draft)
    units.extend((PARSHA_WORK_REF_TITLE, row) for row in parsha_rows)

    parsha_names_en = tuple(row.label_en for row in parsha_rows if row.granularity is Granularity.PARSHA)
    parsha_names_he = tuple(row.label_he for row in parsha_rows if row.granularity is Granularity.PARSHA)
    drafts.extend(build_parsha_work_drafts(parsha_names_en, parsha_names_he))

    drafts = renumber_corpus_seq(drafts)
    if on_progress is not None:
        on_progress("harvesting title aliases", len(specs) + 2, steps)
    aliases = await _harvest_aliases(client, drafts)

    links: tuple[EinMishpatEdge, ...] = ()
    bridged: tuple[EinMishpatEdge, ...] = ()
    if include_links:
        # The long pole: seventeen CSV shards and 118,805 edges, and the reason the whole crawl
        # takes ninety seconds rather than twenty.
        if on_progress is not None:
            on_progress("downloading Ein Mishpat links", len(specs) + 3, steps)
        direct = list(iter_all_ein_mishpat(http))
        links = tuple(direct)
        bridged = tuple(bridge_via_tur(direct))

    payload = SnapshotPayload(
        format_version=FORMAT_VERSION,
        created_at=datetime.now(UTC),
        sefaria_version=datetime.now(UTC).date().isoformat(),
        works=tuple(drafts),
        units=tuple(units),
        aliases=tuple(aliases),
        links=links,
        bridged=bridged,
    )
    return CrawlResult(
        payload=payload,
        unit_count=sum(draft.unit_count for draft in drafts),
        edge_count=len(links) + len(bridged),
    )
