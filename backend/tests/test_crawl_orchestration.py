"""The crawl orchestrator, driven entirely by mocked Sefaria responses.

One handler answers every endpoint the crawl touches, so the whole composition runs without a
network: seven corpora, seven single works, the named work, the parshiyos, the parsha-weekly works
and the alias harvest.
"""

from __future__ import annotations

import httpx
import pytest

from sidra.catalog.corpora import ketuvim_order, shulchan_aruch_order
from sidra.catalog.crawl import crawl_catalog
from sidra.catalog.granularity import Granularity
from sidra.catalog.ingest_aliases import local_aliases
from sidra.catalog.sefaria_client import SefariaClient

PARSHA_REFS = [f"Genesis 1:{n}" for n in range(1, 8)]


def _parsha_index(*names: str) -> dict[str, object]:
    return {
        "alts": {
            "Parasha": {
                "nodes": [
                    {"title": name, "heTitle": f"פ{index}", "wholeRef": f"Genesis {index}", "refs": PARSHA_REFS}
                    for index, name in enumerate(names, start=1)
                ]
            }
        }
    }


GATE_INDEX = {
    "alts": {
        "Gate": {
            "nodes": [
                {"title": "ON PRIDE", "heTitle": "שער הגאווה"},
                {"title": "ON REMORSE", "heTitle": "שער החרטה\n"},
            ]
        }
    }
}
RAW_INDEX = {"schema": {"titles": [{"text": "Alt Spelling", "lang": "en"}]}}
ALIAS_TARGETS = sorted({ref_title for _, ref_title in local_aliases()})


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path

    if "/v2/raw/index/" in path:
        return httpx.Response(200, json=RAW_INDEX)

    if "/index/" in path:
        book = path.rsplit("/", 1)[-1]
        if book == "Orchot Tzadikim":
            return httpx.Response(200, json=GATE_INDEX)
        # 11 + 11 + 11 + 11 + 10 = the 54 parshiyos the spine requires.
        index = ["Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy"].index(book)
        count = 10 if index == 4 else 11
        offset = index * 11
        return httpx.Response(200, json=_parsha_index(*(f"Parsha{offset + n}" for n in range(1, count + 1))))

    # A corpus with an order override names real books, so its shape must supply exactly those.
    for suffix, order, he in (("/Writings", ketuvim_order(), "כ"), ("Shulchan Arukh", shulchan_aruch_order(), "ש")):
        if path.endswith(suffix):
            return httpx.Response(
                200,
                json=[
                    {"title": title, "heTitle": he, "section": suffix.lstrip("/"), "length": 1, "chapters": [3]}
                    for title in order
                ],
            )

    # The Torah shape stands in for every local alias target, so the alias harvest finds them all:
    # local_alias_rows refuses an alias pointing at a missing work, which is exactly the behaviour
    # that catches a typo in the YAML.
    if path.endswith("/Torah"):
        return httpx.Response(
            200,
            json=[
                {"title": title, "heTitle": "ת", "section": "Torah", "length": 1, "chapters": [3]}
                for title in ALIAS_TARGETS
            ],
        )

    # Every other shape call returns two simple nodes.
    return httpx.Response(
        200,
        json=[
            {
                "title": f"Work A {path[-8:]}",
                "heTitle": "א",
                "section": "Seder Zeraim",
                "length": 2,
                "chapters": [3, 4],
            },
            {"title": f"Work B {path[-8:]}", "heTitle": "ב", "section": "Seder Zeraim", "length": 1, "chapters": [5]},
        ],
    )


@pytest.fixture
def client() -> SefariaClient:
    return SefariaClient(
        httpx.AsyncClient(transport=httpx.MockTransport(_handler)),
        "https://www.sefaria.org/api",
        backoff_seconds=0.0,
    )


async def test_the_crawl_composes_every_ingester(client: SefariaClient) -> None:
    with httpx.Client(transport=httpx.MockTransport(_handler)) as http:
        result = await crawl_catalog(client, http, include_links=False)

    payload = result.payload
    corpora_seen = {draft.corpus_id for draft in payload.works}
    assert {"torah", "mussar", "chassidus", "midrash", "parsha_weekly"} <= corpora_seen
    assert result.unit_count == sum(draft.unit_count for draft in payload.works)


async def test_corpus_positions_are_unique(client: SefariaClient) -> None:
    """Several specs share a corpus_id, so without renumbering the unique constraint rejects them."""
    with httpx.Client(transport=httpx.MockTransport(_handler)) as http:
        payload = (await crawl_catalog(client, http, include_links=False)).payload
    positions = [(draft.corpus_id, draft.corpus_seq) for draft in payload.works]
    assert len(set(positions)) == len(positions)


async def test_each_corpus_numbers_from_one(client: SefariaClient) -> None:
    with httpx.Client(transport=httpx.MockTransport(_handler)) as http:
        payload = (await crawl_catalog(client, http, include_links=False)).payload
    for corpus_id in {draft.corpus_id for draft in payload.works}:
        seqs = sorted(d.corpus_seq for d in payload.works if d.corpus_id == corpus_id)
        assert seqs == list(range(1, len(seqs) + 1)), corpus_id


async def test_the_parsha_weekly_works_borrow_the_spine(client: SefariaClient) -> None:
    """Order matters: parshiyos must be ingested before the works that reuse their names."""
    with httpx.Client(transport=httpx.MockTransport(_handler)) as http:
        payload = (await crawl_catalog(client, http, include_links=False)).payload
    weekly = [d for d in payload.works if d.corpus_id == "parsha_weekly"]
    assert len(weekly) == 3
    assert all(draft.unit_count == 54 for draft in weekly)
    assert weekly[0].labels is not None and weekly[0].labels[0].startswith("Parsha")


async def test_stored_units_are_produced_for_the_parshiyos(client: SefariaClient) -> None:
    with httpx.Client(transport=httpx.MockTransport(_handler)) as http:
        payload = (await crawl_catalog(client, http, include_links=False)).payload
    assert payload.units
    assert {work_ref for work_ref, _ in payload.units} == {"Parashat HaShavua"}
    aliyot = [row for _, row in payload.units if row.granularity is Granularity.ALIYAH]
    assert len(aliyot) == 54 * 7


async def test_aliases_are_harvested_from_both_sources(client: SefariaClient) -> None:
    with httpx.Client(transport=httpx.MockTransport(_handler)) as http:
        payload = (await crawl_catalog(client, http, include_links=False)).payload
    sources = {alias.source for alias in payload.aliases}
    assert "sefaria" in sources


async def test_skipping_links_leaves_the_catalog_complete(client: SefariaClient) -> None:
    with httpx.Client(transport=httpx.MockTransport(_handler)) as http:
        result = await crawl_catalog(client, http, include_links=False)
    assert result.edge_count == 0
    assert result.payload.links == ()
    assert result.payload.works


async def test_a_work_whose_raw_index_fails_contributes_no_aliases_but_does_not_stop_the_crawl() -> None:
    def flaky(request: httpx.Request) -> httpx.Response:
        if "/v2/raw/index/" in request.url.path:
            return httpx.Response(200, json={"error": "No book named that."})
        return _handler(request)

    client = SefariaClient(
        httpx.AsyncClient(transport=httpx.MockTransport(flaky)),
        "https://www.sefaria.org/api",
        backoff_seconds=0.0,
    )
    with httpx.Client(transport=httpx.MockTransport(flaky)) as http:
        payload = (await crawl_catalog(client, http, include_links=False)).payload
    assert payload.works
    assert all(alias.source == "local" for alias in payload.aliases)


async def test_including_links_runs_the_extractor_and_the_bridge(client: SefariaClient) -> None:
    """The 656 MB path, with the export stubbed to a handful of rows."""
    header = "Citation 1,Citation 2,Conection Type,Text 1,Text 2,Category 1,Category 2"
    rows = [
        '"Avodah Zarah 38b:4","Tur, Yoreh De\'ah 112",ein mishpat / ner mitsvah,"A","T",Talmud,Halakhah',
        '"Berakhot 2a:1","Mishneh Torah, Reading the Shema 1:1",ein mishpat / ner mitsvah,"B","M",Talmud,Halakhah',
    ]
    body = ("\n".join([header, *rows]) + "\n").encode("utf-8")

    def links_handler(request: httpx.Request) -> httpx.Response:
        if "sefaria-export" in str(request.url):
            return httpx.Response(200, content=body)
        return _handler(request)

    with httpx.Client(transport=httpx.MockTransport(links_handler)) as http:
        result = await crawl_catalog(client, http, include_links=True)

    # Direct and bridged edges are kept apart, so an inference is never written as a citation.
    assert result.edge_count == len(result.payload.links) + len(result.payload.bridged)
    assert result.payload.links
    assert result.payload.bridged
    assert all(edge.citation_2.startswith("Shulchan Arukh, ") for edge in result.payload.bridged)
    assert not any(edge.citation_2.startswith("Shulchan Arukh, ") for edge in result.payload.links)


async def test_the_crawl_reports_progress_when_someone_is_watching(client: SefariaClient) -> None:
    """A ninety-second crawl behind a spinner with nothing in it is what the hook exists to fix."""
    header = "Citation 1,Citation 2,Conection Type,Text 1,Text 2,Category 1,Category 2"
    row = '"Berakhot 2a:1","Mishneh Torah, Reading the Shema 1:1",ein mishpat / ner mitsvah,"B","M",Talmud,Halakhah'
    body = (header + "\n" + row + "\n").encode("utf-8")

    def links_handler(request: httpx.Request) -> httpx.Response:
        if "sefaria-export" in str(request.url):
            return httpx.Response(200, content=body)
        return _handler(request)

    seen: list[tuple[str, int, int]] = []
    with httpx.Client(transport=httpx.MockTransport(links_handler)) as http:
        await crawl_catalog(client, http, include_links=True, on_progress=lambda p, d, t: seen.append((p, d, t)))

    phases = [phase for phase, _, _ in seen]
    assert any(phase.startswith("crawling ") for phase in phases)
    assert "crawling the parsha cycle" in phases
    assert "harvesting title aliases" in phases
    assert "downloading Ein Mishpat links" in phases
    # Monotonic and bounded, so a bar drawn from it never goes backwards or past its own end.
    assert [done for _, done, _ in seen] == sorted(done for _, done, _ in seen)
    assert all(done <= total for _, done, total in seen)


async def test_skipping_the_links_skips_that_step_and_no_other(client: SefariaClient) -> None:
    seen: list[str] = []
    with httpx.Client(transport=httpx.MockTransport(_handler)) as http:
        await crawl_catalog(client, http, include_links=False, on_progress=lambda p, d, t: seen.append(p))

    assert "harvesting title aliases" in seen
    assert "downloading Ein Mishpat links" not in seen
