from __future__ import annotations

import inspect

import httpx
import pytest

from sidra.alignment.ein_mishpat import (
    CONNECTION_TYPE_COLUMN,
    EIN_MISHPAT_TYPE,
    SHARD_COUNT,
    iter_all_ein_mishpat,
    iter_ein_mishpat,
)

# The exact real header row, including Sefaria's one-n typo, with real rows beneath it.
HEADER = "Citation 1,Citation 2,Conection Type,Text 1,Text 2,Category 1,Category 2"
ROWS = [
    '"Avodah Zarah 38b:4","Mishneh Torah, Forbidden Foods 17:13",ein mishpat / ner mitsvah,'
    '"Avodah Zarah","Mishneh Torah, Forbidden Foods",Talmud,Halakhah',
    '"Avodah Zarah 38b:4","Shulchan Arukh, Yoreh De\'ah 112:9",ein mishpat / ner mitsvah,'
    '"Avodah Zarah","Shulchan Arukh, Yoreh De\'ah",Talmud,Halakhah',
    '"Avodah Zarah 38b:4","Tur, Yoreh De\'ah 112",ein mishpat / ner mitsvah,'
    '"Avodah Zarah","Tur, Yoreh De\'ah",Talmud,Halakhah',
    '"A Dictionary of the Talmud, אֱגוֹד 1","Mishnah Peah 6:6",quotation,'
    '"A Dictionary of the Talmud","Mishnah Peah",Reference,Mishnah',
    '"Berakhot 2a:1","Genesis 1:1",,"Berakhot","Genesis",Talmud,Tanakh',
]
CSV_BODY = "\n".join([HEADER, *ROWS]) + "\n"
EMPTY_SHARD = "\n".join([HEADER, ROWS[3], ROWS[4]]) + "\n"


def _client(body: str, *, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body.encode("utf-8"))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_only_ein_mishpat_rows_are_yielded() -> None:
    edges = list(iter_ein_mishpat(0, _client(CSV_BODY)))
    assert len(edges) == 3
    assert all(edge.citation_1 == "Avodah Zarah 38b:4" for edge in edges)


def test_the_quadruple_carries_its_categories() -> None:
    edges = list(iter_ein_mishpat(0, _client(CSV_BODY)))
    assert edges[0].citation_2 == "Mishneh Torah, Forbidden Foods 17:13"
    assert edges[0].category_1 == "Talmud"
    assert edges[0].category_2 == "Halakhah"
    assert {edge.citation_2 for edge in edges} == {
        "Mishneh Torah, Forbidden Foods 17:13",
        "Shulchan Arukh, Yoreh De'ah 112:9",
        "Tur, Yoreh De'ah 112",
    }


def test_the_column_typo_is_load_bearing() -> None:
    """Sefaria's header says 'Conection Type'. Spelling it correctly matches nothing at all."""
    assert CONNECTION_TYPE_COLUMN == "Conection Type"
    corrected = CSV_BODY.replace("Conection Type", "Connection Type")
    assert list(iter_ein_mishpat(0, _client(corrected))) == []


def test_a_shard_with_no_matches_is_normal_not_an_error() -> None:
    """Shard 8 of the real export contains zero Ein Mishpat rows."""
    assert list(iter_ein_mishpat(8, _client(EMPTY_SHARD))) == []


def test_rows_with_an_empty_connection_type_are_skipped() -> None:
    edges = list(iter_ein_mishpat(0, _client(CSV_BODY)))
    assert not any("Genesis" in edge.citation_2 for edge in edges)


@pytest.mark.parametrize("shard", [-1, SHARD_COUNT, 99])
def test_an_out_of_range_shard_raises(shard: int) -> None:
    """links17.csv is a 404, so the range guard fails fast rather than fetching."""
    with pytest.raises(ValueError, match="range 0..16"):
        list(iter_ein_mishpat(shard, _client(CSV_BODY)))


def test_a_real_http_error_propagates() -> None:
    with pytest.raises(httpx.HTTPStatusError):
        list(iter_ein_mishpat(3, _client("", status=404)))


def test_nothing_accumulates() -> None:
    """A refactor to a list must fail here rather than in the memory budget: 656 MB of shards."""
    assert inspect.isgenerator(iter_all_ein_mishpat(_client(CSV_BODY)))
    assert inspect.isgenerator(iter_ein_mishpat(0, _client(CSV_BODY)))


def test_iter_all_walks_every_shard() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=CSV_BODY.encode("utf-8"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    edges = list(iter_all_ein_mishpat(client))
    assert len(seen) == SHARD_COUNT
    assert seen[0].endswith("links0.csv")
    assert seen[-1].endswith("links16.csv")
    assert len(edges) == 3 * SHARD_COUNT


def test_a_body_larger_than_one_chunk_still_parses() -> None:
    """Exercises the streaming adapter across a buffer boundary."""
    filler = "\n".join(f'"Filler {n}","Target {n}",{EIN_MISHPAT_TYPE},"F","T",Talmud,Halakhah' for n in range(2000))
    body = "\n".join([HEADER, filler]) + "\n"
    assert len(list(iter_ein_mishpat(0, _client(body)))) == 2000
