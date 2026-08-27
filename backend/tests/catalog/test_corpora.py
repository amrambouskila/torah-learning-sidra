from __future__ import annotations

import httpx

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.corpora import (
    MISHNAH_COMMENTARY_SECTIONS,
    MISHNEH_TORAH_NON_HILCHOS,
    SHULCHAN_ARUCH_NON_SIMANIM,
    corpora,
    ketuvim_order,
)
from sidra.catalog.ingest import ingest_corpus
from sidra.catalog.sefaria_client import SefariaClient

EXPECTED_CORPUS_IDS = (
    "torah",
    "neviim",
    "ketuvim",
    "mishnah",
    "bavli",
    "mishneh_torah",
    "shulchan_aruch",
)


def test_the_seven_derivable_corpora_are_specified() -> None:
    assert tuple(spec.corpus_id for spec in corpora()) == EXPECTED_CORPUS_IDS


def test_ketuvim_order_holds_thirteen_books_with_koheles_among_the_megillos() -> None:
    order = ketuvim_order()
    assert len(order) == 13
    assert order[0] == "Psalms"
    assert order[-1] == "II Chronicles"
    assert order.index("Ecclesiastes") < order.index("Esther")
    assert order[-1] != "Ecclesiastes"


def test_ketuvim_order_is_cached() -> None:
    assert ketuvim_order() is ketuvim_order()


def test_the_ketuvim_spec_carries_the_override() -> None:
    spec = next(s for s in corpora() if s.corpus_id == "ketuvim")
    assert spec.order_override == ketuvim_order()


def test_bavli_filters_to_the_sedarim() -> None:
    """Without this the shape yields 57 works: Minor Tractates, Guides and Tziyyun LeNefesh Chayyah."""
    spec = next(s for s in corpora() if s.corpus_id == "bavli")
    assert spec.include_section_prefix == "Seder "
    assert spec.address_scheme is AddressScheme.DAF_AMUD


def test_mishneh_torah_excludes_the_six_non_hilchos_nodes() -> None:
    """Four are the Rambam's front matter; Kuntres Zikah and Steinsaltz are not the Rambam."""
    spec = next(s for s in corpora() if s.corpus_id == "mishneh_torah")
    assert spec.exclude_titles == MISHNEH_TORAH_NON_HILCHOS
    assert len(MISHNEH_TORAH_NON_HILCHOS) == 6
    assert "Kuntres Zikah" in MISHNEH_TORAH_NON_HILCHOS
    assert spec.address_scheme is AddressScheme.NESTED


def test_shulchan_aruch_expands_complex_nodes_and_drops_the_introduction() -> None:
    spec = next(s for s in corpora() if s.corpus_id == "shulchan_aruch")
    assert spec.expand_complex is True
    assert "Shulchan Arukh, Introduction" in spec.exclude_titles


def test_mishnah_excludes_every_commentary_category() -> None:
    spec = next(s for s in corpora() if s.corpus_id == "mishnah")
    assert spec.exclude_sections == MISHNAH_COMMENTARY_SECTIONS
    assert len(MISHNAH_COMMENTARY_SECTIONS) == 3


async def test_ingest_corpus_fetches_and_builds_drafts() -> None:
    """The async wrapper: one shape call, then the pure draft builder."""
    payload = [
        {"title": "Joshua", "heTitle": "יהושע", "section": "Prophets", "length": 2, "chapters": [18, 24]},
        {"title": "Judges", "heTitle": "שופטים", "section": "Prophets", "length": 1, "chapters": [36]},
    ]
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json=payload)

    client = SefariaClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)), "https://www.sefaria.org/api")
    spec = next(s for s in corpora() if s.corpus_id == "neviim")
    drafts = await ingest_corpus(client, spec)

    assert seen == ["/api/shape/Tanakh/Prophets"]
    assert [d.ref_title for d in drafts] == ["Joshua", "Judges"]
    assert [d.unit_count for d in drafts] == [2, 1]


def test_the_shulchan_aruch_excludes_its_two_appendices() -> None:
    """Seder HaGet and Seder Halitzah are procedural orders appended to Even HaEzer, not simanim.
    Counting them gave 1,707 against the measured 1,705."""
    spec = next(item for item in corpora() if item.corpus_id == "shulchan_aruch")
    assert spec.exclude_titles == SHULCHAN_ARUCH_NON_SIMANIM
    assert "Shulchan Arukh, Even HaEzer, Seder HaGet" in SHULCHAN_ARUCH_NON_SIMANIM
    assert "Shulchan Arukh, Even HaEzer, Seder Halitzah" in SHULCHAN_ARUCH_NON_SIMANIM


def test_an_appendix_is_excluded_after_its_parent_is_expanded() -> None:
    """Even HaEzer is a complex node: Seder HaGet and Seder Halitzah only exist as titles once it
    has been split, so a filter that ran only on the parent let them straight through."""
    from sidra.catalog.ingest import _selected
    from sidra.catalog.shape import ShapeNode

    def node(title: str, chapters: list[int], children: list[ShapeNode] | None = None) -> ShapeNode:
        return ShapeNode(
            title=title,
            title_he=f"he-{title}",
            section="Halakhah",
            length=sum(chapters),
            chapters=chapters,
            is_complex=children is not None,
            children=children or [],
        )

    even_haezer = node(
        "Shulchan Arukh, Even HaEzer",
        [178, 1, 1],
        [
            node("Shulchan Arukh, Even HaEzer", [178]),
            node("Shulchan Arukh, Even HaEzer, Seder HaGet", [1]),
            node("Shulchan Arukh, Even HaEzer, Seder Halitzah", [1]),
        ],
    )
    spec = next(item for item in corpora() if item.corpus_id == "shulchan_aruch")
    kept = _selected([even_haezer], spec)
    assert [child.title for child in kept] == ["Shulchan Arukh, Even HaEzer"]
