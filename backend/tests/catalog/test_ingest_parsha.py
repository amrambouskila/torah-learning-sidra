from __future__ import annotations

import pytest

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.catalog.ingest_parsha import aliyah_names, build_parsha_draft, build_parsha_units
from sidra.catalog.parasha_node import ALIYOT_PER_PARSHA, parse_parasha_nodes

# Trimmed but structurally faithful: /api/index/Deuteronomy carries alts.Parasha.nodes, each with
# title, heTitle, wholeRef and exactly seven refs. Ki Tavo's are the real ones.
KI_TAVO_REFS = [
    "Deuteronomy 26:1-26:11",
    "Deuteronomy 26:12-26:15",
    "Deuteronomy 26:16-26:19",
    "Deuteronomy 27:1-27:10",
    "Deuteronomy 27:11-28:6",
    "Deuteronomy 28:7-28:69",
    "Deuteronomy 29:1-29:8",
]
DEUTERONOMY = {
    "title": "Deuteronomy",
    "alts": {
        "Parasha": {
            "nodes": [
                {
                    "title": "Ki Tavo",
                    "heTitle": "כי תבוא",
                    "wholeRef": "Deuteronomy 26:1-29:8",
                    "refs": KI_TAVO_REFS,
                },
                {
                    "title": "Nitzavim",
                    "heTitle": "נצבים",
                    "wholeRef": "Deuteronomy 29:9-30:20",
                    "refs": [f"Deuteronomy 29:{n}" for n in range(9, 16)],
                },
            ]
        }
    },
}


def test_the_parser_reads_alts_parasha() -> None:
    nodes = parse_parasha_nodes(DEUTERONOMY)
    assert [node.title_en for node in nodes] == ["Ki Tavo", "Nitzavim"]
    assert nodes[0].title_he == "כי תבוא"
    assert nodes[0].whole_ref == "Deuteronomy 26:1-29:8"


def test_every_parsha_carries_exactly_seven_aliyot() -> None:
    assert all(len(node.aliyah_refs) == ALIYOT_PER_PARSHA for node in parse_parasha_nodes(DEUTERONOMY))


def test_a_parsha_with_the_wrong_aliyah_count_raises() -> None:
    """Sefaria is consistent at seven. A change should fail loudly, not produce a short parsha."""
    payload = {"alts": {"Parasha": {"nodes": [{"title": "Broken", "heTitle": "x", "refs": ["a", "b"]}]}}}
    with pytest.raises(ValueError, match="expected 7 aliyot, found 2"):
        parse_parasha_nodes(payload)


def test_a_payload_without_alts_raises_a_clear_error_not_a_keyerror() -> None:
    with pytest.raises(ValueError, match="alts"):
        parse_parasha_nodes({"title": "Deuteronomy"})


def test_a_payload_whose_alts_lacks_parasha_raises() -> None:
    with pytest.raises(ValueError, match="alts"):
        parse_parasha_nodes({"alts": {"Chapters": {}}})


def test_the_aliyah_names_override_holds_seven_entries() -> None:
    """Seven, not eight: maftir is deferred past P1 because it lives only in /api/calendars."""
    names = aliyah_names()
    assert len(names) == ALIYOT_PER_PARSHA
    assert [n.en for n in names] == ["Rishon", "Sheni", "Shlishi", "Revii", "Chamishi", "Shishi", "Shvii"]
    assert names[2].he == "שלישי"


def test_aliyah_names_are_cached() -> None:
    assert aliyah_names() is aliyah_names()


def test_units_interleave_each_parsha_with_its_seven_aliyot() -> None:
    rows = build_parsha_units(parse_parasha_nodes(DEUTERONOMY))
    assert len(rows) == 2 * (1 + ALIYOT_PER_PARSHA)
    assert rows[0].granularity is Granularity.PARSHA
    assert rows[0].parent_seq is None
    assert all(row.parent_seq == 1 for row in rows[1:8])
    assert all(row.granularity is Granularity.ALIYAH for row in rows[1:8])
    assert rows[8].granularity is Granularity.PARSHA
    assert rows[8].parent_seq is None


def test_resolved_ref_is_sefarias_own_string_never_synthesized() -> None:
    """The spec forbids building a range ref. Ki Tavo Shlishi must be Sefaria's exact string."""
    rows = build_parsha_units(parse_parasha_nodes(DEUTERONOMY))
    shlishi = next(r for r in rows if r.label_en == "Shlishi")
    assert shlishi.resolved_ref == "Deuteronomy 26:16-26:19"
    assert shlishi.resolved_ref in KI_TAVO_REFS
    assert shlishi.label_he == "שלישי"
    assert shlishi.ordinal == 3


def test_addr_types_use_sefaria_vocabulary_not_granularity() -> None:
    rows = build_parsha_units(parse_parasha_nodes(DEUTERONOMY))
    assert rows[0].addr_types == ("Parasha",)
    assert rows[1].addr_types == ("Aliyah",)
    assert all(isinstance(component, str) for row in rows for component in row.addr_types)


def test_a_parsha_row_carries_the_whole_ref() -> None:
    rows = build_parsha_units(parse_parasha_nodes(DEUTERONOMY))
    assert rows[0].resolved_ref == "Deuteronomy 26:1-29:8"
    assert rows[0].is_range is True


def test_the_draft_is_a_stored_scheme_work() -> None:
    draft = build_parsha_draft(432)
    assert draft.address_scheme is AddressScheme.STORED
    assert draft.corpus_id == "torah"
    assert draft.unit_count == 432
    assert draft.title_he == "פרשת השבוע"


async def test_ingest_parshiyos_walks_all_five_chumashim() -> None:
    """The async wrapper: five index calls, then the pure row builder."""
    import httpx

    from sidra.catalog.ingest_parsha import CHUMASH_BOOKS, ingest_parshiyos
    from sidra.catalog.sefaria_client import SefariaClient

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path.rsplit("/", 1)[-1])
        return httpx.Response(200, json=DEUTERONOMY)

    client = SefariaClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)), "https://www.sefaria.org/api")
    draft, rows = await ingest_parshiyos(client)

    assert seen == list(CHUMASH_BOOKS)
    assert len(rows) == 5 * 2 * (1 + ALIYOT_PER_PARSHA)
    assert draft.unit_count == len(rows)
    assert rows[0].seq == 1
    assert rows[-1].seq == len(rows)
