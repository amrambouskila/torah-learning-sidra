from __future__ import annotations

from sidra.alignment.ein_mishpat import EinMishpatEdge
from sidra.alignment.tur_bridge import bridge_via_tur

ANCHOR = "Avodah Zarah 38b:4"
OTHER = "Avodah Zarah 38b:13"


def _edge(anchor: str, target: str) -> EinMishpatEdge:
    return EinMishpatEdge(anchor, target, "Talmud", "Halakhah")


def test_an_anchor_citing_tur_but_not_shulchan_aruch_is_bridged() -> None:
    bridged = bridge_via_tur([_edge(ANCHOR, "Tur, Yoreh De'ah 112")])
    assert len(bridged) == 1
    assert bridged[0].citation_1 == ANCHOR
    assert bridged[0].citation_2 == "Shulchan Arukh, Yoreh De'ah 112"
    assert bridged[0].category_2 == "Halakhah"


def test_an_anchor_that_already_reaches_shulchan_aruch_is_left_alone() -> None:
    """Never duplicate a direct citation with an inference."""
    edges = [_edge(ANCHOR, "Tur, Yoreh De'ah 112"), _edge(ANCHOR, "Shulchan Arukh, Yoreh De'ah 112:9")]
    assert bridge_via_tur(edges) == []


def test_an_anchor_with_neither_yields_nothing() -> None:
    assert bridge_via_tur([_edge(ANCHOR, "Mishneh Torah, Forbidden Foods 17:13")]) == []


def test_each_anchor_is_judged_independently() -> None:
    edges = [
        _edge(ANCHOR, "Tur, Yoreh De'ah 112"),
        _edge(ANCHOR, "Shulchan Arukh, Yoreh De'ah 112:9"),
        _edge(OTHER, "Tur, Yoreh De'ah 103"),
    ]
    bridged = bridge_via_tur(edges)
    assert [e.citation_1 for e in bridged] == [OTHER]
    assert bridged[0].citation_2 == "Shulchan Arukh, Yoreh De'ah 103"


def test_the_inferred_ref_is_siman_level_with_no_seif() -> None:
    """Tur has no seifim, so nothing can be carried across at seif granularity."""
    bridged = bridge_via_tur([_edge(ANCHOR, "Tur, Orach Chayim 2")])
    assert bridged[0].citation_2 == "Shulchan Arukh, Orach Chayim 2"
    assert ":" not in bridged[0].citation_2.rsplit(" ", 1)[-1]


def test_a_malformed_tur_ref_is_skipped_rather_than_guessed() -> None:
    assert bridge_via_tur([_edge(ANCHOR, "Tur, Yoreh De'ah")]) == []
    assert bridge_via_tur([_edge(ANCHOR, "Tur")]) == []


def test_all_four_chalakim_bridge() -> None:
    chalakim = ["Orach Chayim", "Yoreh De'ah", "Even HaEzer", "Choshen Mishpat"]
    edges = [_edge(f"Anchor {n}", f"Tur, {chelek} {n + 1}") for n, chelek in enumerate(chalakim)]
    bridged = sorted(e.citation_2 for e in bridge_via_tur(edges))
    assert bridged == sorted(
        [
            "Shulchan Arukh, Orach Chayim 1",
            "Shulchan Arukh, Yoreh De'ah 2",
            "Shulchan Arukh, Even HaEzer 3",
            "Shulchan Arukh, Choshen Mishpat 4",
        ]
    )
