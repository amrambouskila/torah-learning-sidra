"""Read and write the committed catalog snapshot.

The snapshot is what makes the catalog reproducible offline. ``sidra_db seed`` rebuilds every row
from it in seconds, on any machine, with no network -- so a fresh checkout gets byte-identical data
rather than whatever Sefaria happens to return that day.

JSONL, one record per line: streamable, diffable line by line, and it never requires holding
118,805 edges in a single JSON array to read or write.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sidra.alignment.ein_mishpat import EinMishpatEdge
from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.catalog.ingest_aliases import AliasRow
from sidra.catalog.stored_unit import StoredUnitRow
from sidra.catalog.work_draft import WorkDraft

FORMAT_VERSION = 1

KIND_HEADER = "header"
KIND_WORK = "work"
KIND_UNIT = "unit"
KIND_ALIAS = "alias"
KIND_LINK = "link"
KIND_BRIDGED = "bridged"

_JSON_ARGS: dict[str, Any] = {"ensure_ascii": False, "sort_keys": True, "separators": (",", ":")}
"""Fixed so two writes of the same input are byte-identical."""


DEFAULT_SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "data" / "snapshots" / "p1.jsonl"
"""The committed snapshot the catalog rebuilds from. One definition; the CLI and the API share it."""


@dataclass(frozen=True, slots=True)
class SnapshotPayload:
    format_version: int
    created_at: datetime
    sefaria_version: str
    works: tuple[WorkDraft, ...]
    units: tuple[tuple[str, StoredUnitRow], ...]
    aliases: tuple[AliasRow, ...]
    links: tuple[EinMishpatEdge, ...]
    bridged: tuple[EinMishpatEdge, ...] = ()
    """Tur-bridge inferences, kept apart so they are never written as direct citations."""


def _work_record(draft: WorkDraft) -> dict[str, Any]:
    return {
        "kind": KIND_WORK,
        "corpus_id": draft.corpus_id,
        "corpus_seq": draft.corpus_seq,
        "index_title": draft.index_title,
        "ref_title": draft.ref_title,
        "title_he": draft.title_he,
        "granularity": str(draft.granularity),
        "address_scheme": str(draft.address_scheme),
        "shape": list(draft.shape),
        "labels": list(draft.labels) if draft.labels is not None else None,
        "labels_he": list(draft.labels_he) if draft.labels_he is not None else None,
        "unit_count": draft.unit_count,
        "source": draft.source,
    }


def _read_work(record: dict[str, Any]) -> WorkDraft:
    return WorkDraft(
        corpus_id=record["corpus_id"],
        corpus_seq=record["corpus_seq"],
        index_title=record["index_title"],
        ref_title=record["ref_title"],
        title_he=record["title_he"],
        granularity=Granularity(record["granularity"]),
        address_scheme=AddressScheme(record["address_scheme"]),
        shape=tuple(record["shape"]),
        labels=tuple(record["labels"]) if record["labels"] is not None else None,
        unit_count=record["unit_count"],
        source=record["source"],
        labels_he=tuple(record["labels_he"]) if record["labels_he"] is not None else None,
    )


def _unit_record(work_ref_title: str, row: StoredUnitRow) -> dict[str, Any]:
    return {
        "kind": KIND_UNIT,
        "work_ref_title": work_ref_title,
        "seq": row.seq,
        "parent_seq": row.parent_seq,
        "addr": list(row.addr),
        "addr_types": list(row.addr_types),
        "granularity": str(row.granularity),
        "label_en": row.label_en,
        "label_he": row.label_he,
        "ordinal": row.ordinal,
        "is_range": row.is_range,
        "resolved_ref": row.resolved_ref,
        "resolved_he_ref": row.resolved_he_ref,
        "child_count": row.child_count,
    }


def _read_unit(record: dict[str, Any]) -> tuple[str, StoredUnitRow]:
    return record["work_ref_title"], StoredUnitRow(
        seq=record["seq"],
        parent_seq=record["parent_seq"],
        addr=tuple(record["addr"]),
        addr_types=tuple(record["addr_types"]),
        granularity=Granularity(record["granularity"]),
        label_en=record["label_en"],
        label_he=record["label_he"],
        ordinal=record["ordinal"],
        is_range=record["is_range"],
        resolved_ref=record["resolved_ref"],
        resolved_he_ref=record["resolved_he_ref"],
        child_count=record["child_count"],
    )


def _records(payload: SnapshotPayload) -> Iterator[dict[str, Any]]:
    yield {
        "kind": KIND_HEADER,
        "format_version": payload.format_version,
        "created_at": payload.created_at.isoformat(),
        "sefaria_version": payload.sefaria_version,
    }
    for draft in payload.works:
        yield _work_record(draft)
    for work_ref_title, row in payload.units:
        yield _unit_record(work_ref_title, row)
    for alias in payload.aliases:
        yield {
            "kind": KIND_ALIAS,
            "ref_title": alias.ref_title,
            "alias": alias.alias,
            "lang": alias.lang,
            "source": alias.source,
        }
    for kind, edges in ((KIND_LINK, payload.links), (KIND_BRIDGED, payload.bridged)):
        for edge in edges:
            yield {
                "kind": kind,
                "citation_1": edge.citation_1,
                "citation_2": edge.citation_2,
                "category_1": edge.category_1,
                "category_2": edge.category_2,
            }


def write_snapshot(path: Path, payload: SnapshotPayload) -> None:
    """Write a snapshot. Two writes of the same payload are byte-identical."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in _records(payload):
            handle.write(json.dumps(record, **_JSON_ARGS) + "\n")


def read_snapshot(path: Path) -> SnapshotPayload:
    """Read a snapshot back, parsing ``created_at`` to a timezone-aware datetime.

    asyncpg rejects a string for a timestamptz column, so the parse happens here rather than
    surfacing as a driver error at insert time.
    """
    header: dict[str, Any] | None = None
    works: list[WorkDraft] = []
    units: list[tuple[str, StoredUnitRow]] = []
    aliases: list[AliasRow] = []
    links: list[EinMishpatEdge] = []
    bridged: list[EinMishpatEdge] = []

    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{number}: not valid JSON ({error.msg})") from error

            kind = record.get("kind")
            if kind == KIND_HEADER:
                header = record
            elif kind == KIND_WORK:
                works.append(_read_work(record))
            elif kind == KIND_UNIT:
                units.append(_read_unit(record))
            elif kind == KIND_ALIAS:
                aliases.append(
                    AliasRow(
                        ref_title=record["ref_title"],
                        alias=record["alias"],
                        lang=record["lang"],
                        source=record["source"],
                    )
                )
            elif kind in (KIND_LINK, KIND_BRIDGED):
                edge = EinMishpatEdge(
                    citation_1=record["citation_1"],
                    citation_2=record["citation_2"],
                    category_1=record["category_1"],
                    category_2=record["category_2"],
                )
                (links if kind == KIND_LINK else bridged).append(edge)
            else:
                raise ValueError(f"{path}:{number}: unknown record kind {kind!r}")

    if header is None:
        raise ValueError(f"{path}: no header record; the file is truncated or not a snapshot")
    if header["format_version"] != FORMAT_VERSION:
        raise ValueError(
            f"{path}: snapshot format version {header['format_version']}, this build reads {FORMAT_VERSION}"
        )

    return SnapshotPayload(
        format_version=header["format_version"],
        created_at=datetime.fromisoformat(header["created_at"]),
        sefaria_version=header["sefaria_version"],
        works=tuple(works),
        units=tuple(units),
        aliases=tuple(aliases),
        links=tuple(links),
        bridged=tuple(bridged),
    )
