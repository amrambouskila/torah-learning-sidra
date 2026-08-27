"""Ingest the parshiyos and their aliyot.

These are the one part of Chumash that cannot be derived. An aliyah carries Sefaria's own range
expansion -- ``Deuteronomy, Ki Tavo 3`` resolves to ``Deuteronomy 26:16-26:19`` -- and the spec
forbids synthesizing a range ref, because Sefaria's range-tail compression is undocumented and not
reversibly derivable. So aliyot and parshiyos are stored rows, 432 of them.

**Maftir is deferred past P1.** The index alt-struct carries exactly seven aliyot per parsha; the
eighth reading appears only in ``/api/calendars`` ``extraDetails.aliyot[7]``, which would mean a
call per week rather than five calls in total. P2 needs it for the weekly Chumash target and can
add it then.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.catalog.parasha_node import ParashaNode, parse_parasha_nodes
from sidra.catalog.sefaria_client import SefariaClient
from sidra.catalog.stored_unit import StoredUnitRow
from sidra.catalog.work_draft import WorkDraft

OVERRIDES_DIR = Path(__file__).parent / "overrides"

CHUMASH_BOOKS = ("Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy")
PARSHA_ADDR_TYPE = "Parasha"
ALIYAH_ADDR_TYPE = "Aliyah"


@dataclass(frozen=True, slots=True)
class AliyahName:
    ordinal: int
    en: str
    he: str


@lru_cache(maxsize=1)
def aliyah_names() -> tuple[AliyahName, ...]:
    payload = yaml.safe_load((OVERRIDES_DIR / "aliyah_names.yaml").read_text(encoding="utf-8"))
    return tuple(AliyahName(ordinal=e["ordinal"], en=e["en"], he=e["he"]) for e in payload["aliyot"])


def build_parsha_units(nodes: list[ParashaNode]) -> list[StoredUnitRow]:
    """Turn parsha nodes into stored rows: each parsha, then its seven aliyot as children.

    ``resolved_ref`` is Sefaria's own string, copied verbatim. Nothing here builds a range.
    """
    names = aliyah_names()
    rows: list[StoredUnitRow] = []
    seq = 0
    for node in nodes:
        seq += 1
        parsha_seq = seq
        rows.append(
            StoredUnitRow(
                seq=parsha_seq,
                parent_seq=None,
                addr=(),
                addr_types=(PARSHA_ADDR_TYPE,),
                granularity=Granularity.PARSHA,
                label_en=node.title_en,
                label_he=node.title_he,
                ordinal=None,
                is_range=True,
                resolved_ref=node.whole_ref,
            )
        )
        for name, aliyah_ref in zip(names, node.aliyah_refs, strict=True):
            seq += 1
            rows.append(
                StoredUnitRow(
                    seq=seq,
                    parent_seq=parsha_seq,
                    addr=(str(name.ordinal),),
                    addr_types=(ALIYAH_ADDR_TYPE,),
                    granularity=Granularity.ALIYAH,
                    label_en=name.en,
                    label_he=name.he,
                    ordinal=name.ordinal,
                    is_range=True,
                    resolved_ref=aliyah_ref,
                )
            )
    return rows


def build_parsha_draft(unit_count: int) -> WorkDraft:
    """One work holding the whole parsha cycle, at STORED scheme."""
    return WorkDraft(
        corpus_id="torah",
        corpus_seq=100,
        index_title=None,
        ref_title="Parashat HaShavua",
        title_he="פרשת השבוע",
        granularity=Granularity.PARSHA,
        address_scheme=AddressScheme.STORED,
        shape=(),
        labels=None,
        unit_count=unit_count,
        source="sefaria",
    )


async def ingest_parshiyos(client: SefariaClient) -> tuple[WorkDraft, list[StoredUnitRow]]:
    """Read every chumash's Parasha alt-struct and build the 54 parshiyos with their 378 aliyot."""
    nodes: list[ParashaNode] = []
    for book in CHUMASH_BOOKS:
        nodes.extend(parse_parasha_nodes(await client.index(book)))
    rows = build_parsha_units(nodes)
    return build_parsha_draft(len(rows)), rows
