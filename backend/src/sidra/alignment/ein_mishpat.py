"""Extract Ein Mishpat Ner Mitzvah edges from Sefaria's bulk link export.

Ein Mishpat is the classical marginal apparatus mapping every halachic sugya to Rambam, Semag, Tur
and Shulchan Aruch. Sefaria has digitised it as a link *type* -- it is not a text, has no index,
and the links data is the only access path.

The export is 17 CSV shards totalling roughly 656 MB. They are streamed and filtered, never
buffered: 118,805 edges come out in about 50 seconds, against 1.5 to 3 hours of crawling
``/api/links/`` per daf.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from typing import NamedTuple

import httpx

EIN_MISHPAT_TYPE = "ein mishpat / ner mitsvah"
LINKS_URL_TEMPLATE = "https://storage.googleapis.com/sefaria-export/links/links{shard}.csv"
SHARD_COUNT = 17
"""links0.csv through links16.csv. links17.csv is a 404."""

CONNECTION_TYPE_COLUMN = "Conection Type"
"""Sefaria's own typo, with one 'n'. Load-bearing: "Connection Type" matches nothing at all."""

CITATION_1_COLUMN = "Citation 1"
CITATION_2_COLUMN = "Citation 2"
CATEGORY_1_COLUMN = "Category 1"
CATEGORY_2_COLUMN = "Category 2"

_CSV_FIELD_LIMIT = 10_000_000


class EinMishpatEdge(NamedTuple):
    """One Ein Mishpat citation, as the export records it."""

    citation_1: str
    citation_2: str
    category_1: str
    category_2: str


class _IteratorStream(io.RawIOBase):
    """Adapt an iterator of byte chunks to a readable file object.

    This is what keeps the extractor streaming. Buffering a shard would mean holding tens of
    megabytes for the sake of a few thousand matching rows.
    """

    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._chunks = chunks
        self._buffer = b""

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: memoryview) -> int:  # type: ignore[override]
        wanted = len(buffer)
        while len(self._buffer) < wanted:
            try:
                self._buffer += next(self._chunks)
            except StopIteration:
                break
        chunk, self._buffer = self._buffer[:wanted], self._buffer[wanted:]
        buffer[: len(chunk)] = chunk
        return len(chunk)


def _rows(text_stream: io.TextIOBase) -> Iterator[EinMishpatEdge]:
    csv.field_size_limit(_CSV_FIELD_LIMIT)
    for row in csv.DictReader(text_stream):
        if (row.get(CONNECTION_TYPE_COLUMN) or "").strip() != EIN_MISHPAT_TYPE:
            continue
        yield EinMishpatEdge(
            citation_1=row[CITATION_1_COLUMN],
            citation_2=row[CITATION_2_COLUMN],
            category_1=row.get(CATEGORY_1_COLUMN, ""),
            category_2=row.get(CATEGORY_2_COLUMN, ""),
        )


def iter_ein_mishpat(shard: int, client: httpx.Client) -> Iterator[EinMishpatEdge]:
    """Yield the Ein Mishpat edges in one shard.

    A shard with no matching rows yields nothing and does not raise -- shard 8 is genuinely empty,
    which is normal rather than an error.
    """
    if not 0 <= shard < SHARD_COUNT:
        raise ValueError(f"shard must be in range 0..{SHARD_COUNT - 1}, got {shard}")

    with client.stream("GET", LINKS_URL_TEMPLATE.format(shard=shard)) as response:
        response.raise_for_status()
        raw = io.BufferedReader(_IteratorStream(response.iter_bytes()))  # type: ignore[arg-type]
        yield from _rows(io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline=""))


def iter_all_ein_mishpat(client: httpx.Client) -> Iterator[EinMishpatEdge]:
    """Yield every Ein Mishpat edge across all 17 shards.

    Rows are ordered alphabetically by ``Citation 1``, so one masechta's edges can straddle shards.
    Never assume locality.
    """
    for shard in range(SHARD_COUNT):
        yield from iter_ein_mishpat(shard, client)
