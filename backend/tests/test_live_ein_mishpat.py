"""Extract the whole Ein Mishpat map from the real bulk export.

Moves ~656 MB and takes about a minute. Marked ``live`` and excluded from CI.

Run deliberately:  uv run pytest -m live -k ein_mishpat
"""

from __future__ import annotations

import collections

import httpx
import pytest

from sidra.alignment.ein_mishpat import SHARD_COUNT, EinMishpatEdge, iter_all_ein_mishpat

pytestmark = pytest.mark.live

TOTAL_EDGES = 118_805
EDGE_DIRECTIONS = {
    ("Talmud", "Halakhah"): 59_400,
    ("Halakhah", "Halakhah"): 42_584,
    ("Halakhah", "Talmud"): 16_821,
}


@pytest.fixture(scope="session")
def edges() -> list[EinMishpatEdge]:
    with httpx.Client(timeout=300.0) as client:
        return list(iter_all_ein_mishpat(client))


def test_the_export_holds_one_hundred_eighteen_thousand_eight_hundred_five_edges(
    edges: list[EinMishpatEdge],
) -> None:
    assert len(edges) == TOTAL_EDGES


def test_the_edge_directions_match_the_measured_split(edges: list[EinMishpatEdge]) -> None:
    counts = collections.Counter((edge.category_1, edge.category_2) for edge in edges)
    for direction, expected in EDGE_DIRECTIONS.items():
        assert counts[direction] == expected, direction


def test_shard_eight_is_genuinely_empty() -> None:
    from sidra.alignment.ein_mishpat import iter_ein_mishpat

    with httpx.Client(timeout=300.0) as client:
        assert list(iter_ein_mishpat(8, client)) == []


def test_shard_seventeen_does_not_exist() -> None:
    with httpx.Client(timeout=60.0) as client:
        response = client.head("https://storage.googleapis.com/sefaria-export/links/links17.csv")
    assert response.status_code == 404
    assert SHARD_COUNT == 17


def test_the_avodah_zarah_quadruple_is_present(edges: list[EinMishpatEdge]) -> None:
    """The classic Ein Mishpat grouping: Rambam, Semag, Tur and Shulchan Aruch on one anchor."""
    targets = {e.citation_2 for e in edges if e.citation_1 == "Avodah Zarah 38b:4"}
    assert "Mishneh Torah, Forbidden Foods 17:13" in targets
    assert "Shulchan Arukh, Yoreh De'ah 112:9" in targets
    assert "Tur, Yoreh De'ah 112" in targets


def test_deos_five_eight_round_trips_with_shulchan_aruch(edges: list[EinMishpatEdge]) -> None:
    """The graph is symmetric: it traverses from either vertex."""
    forward = {e.citation_2 for e in edges if e.citation_1 == "Mishneh Torah, Human Dispositions 5:8"}
    backward = {e.citation_1 for e in edges if e.citation_2 == "Mishneh Torah, Human Dispositions 5:8"}
    assert "Shulchan Arukh, Orach Chayim 2:6" in forward | backward


HILCHOS_AVODA_ZARA = "Mishneh Torah, Foreign Worship and Customs of the Nations"


def test_the_gemara_queue_ranks_avodah_zarah_first(edges: list[EinMishpatEdge]) -> None:
    """The real aggregate behind Rabbi Jacob's current hilchos."""
    from sidra.alignment.aggregate import rank_masechtos

    ranks = rank_masechtos(edges, HILCHOS_AVODA_ZARA)
    assert ranks[0].masechta == "Avodah Zarah"
    assert ranks[1].masechta == "Sanhedrin"
    assert ranks[0].links == 200
    assert ranks[1].links == 128
    assert sum(rank.links for rank in ranks) == 471
    assert len(ranks) == 29
    assert ranks[0].share == pytest.approx(0.425, abs=0.001)
    assert ranks[1].share == pytest.approx(0.272, abs=0.001)


def test_proposal_confidence_varies_by_hilchos(edges: list[EinMishpatEdge]) -> None:
    """Krias Shema is unambiguous; Teshuva is diffuse. The UI must not present them alike."""
    from sidra.alignment.aggregate import rank_masechtos

    krias_shema = rank_masechtos(edges, "Mishneh Torah, Reading the Shema")
    teshuva = rank_masechtos(edges, "Mishneh Torah, Repentance")
    assert krias_shema[0].masechta == "Berakhot"
    assert krias_shema[0].share > 0.6
    assert teshuva[0].share < 0.25


def test_rambam_coverage_far_exceeds_shulchan_aruch_coverage(edges: list[EinMishpatEdge]) -> None:
    """Structural, not a data defect. Recorded so nobody later 'fixes' it."""
    horayot = [e for e in edges if e.citation_1.startswith("Horayot ") or e.citation_2.startswith("Horayot ")]
    targets = [e.citation_2 if e.citation_1.startswith("Horayot ") else e.citation_1 for e in horayot]
    rambam = sum(1 for t in targets if t.startswith("Mishneh Torah, "))
    shulchan = sum(1 for t in targets if t.startswith("Shulchan Arukh, "))
    assert rambam > shulchan * 5


def test_the_tur_bridge_recovers_missing_shulchan_aruch_edges(edges: list[EinMishpatEdge]) -> None:
    from sidra.alignment.tur_bridge import bridge_via_tur

    bridged = bridge_via_tur(edges)
    assert bridged, "the bridge should recover edges from a partial Shulchan Aruch map"
    assert all(e.citation_2.startswith("Shulchan Arukh, ") for e in bridged)
    direct = {(e.citation_1, e.citation_2) for e in edges}
    assert not any((e.citation_1, e.citation_2) in direct for e in bridged)
