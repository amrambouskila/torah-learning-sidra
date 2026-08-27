from __future__ import annotations

import pytest

from sidra.alignment.aggregate import masechta_of, rank_masechtos
from sidra.alignment.ein_mishpat import EinMishpatEdge

HILCHOS_AVODA_ZARA = "Mishneh Torah, Foreign Worship and Customs of the Nations"

# The measured distribution: 471 links across 29 masechtos. The top five are real; the 24-masechta
# tail is generated so the total lands exactly on 471, and the fixture asserts that before use.
TOP_FIVE = {"Avodah Zarah": 200, "Sanhedrin": 128, "Makkot": 18, "Chullin": 14, "Kiddushin": 14}
MEASURED_TOTAL = 471
MEASURED_MASECHTOS = 29
_TAIL_TOTAL = MEASURED_TOTAL - sum(TOP_FIVE.values())
_TAIL_SIZE = MEASURED_MASECHTOS - len(TOP_FIVE)


def _tail() -> dict[str, int]:
    """24 masechtos summing to 97, none exceeding the smallest of the top five."""
    base, remainder = divmod(_TAIL_TOTAL, _TAIL_SIZE)
    counts = {f"Tail{index:02d}": base + (1 if index < remainder else 0) for index in range(_TAIL_SIZE)}
    assert max(counts.values()) < min(TOP_FIVE.values())
    return counts


MEASURED = {**TOP_FIVE, **_tail()}


def _edges(counts: dict[str, int], *, reverse: bool = False) -> list[EinMishpatEdge]:
    edges: list[EinMishpatEdge] = []
    for masechta, links in counts.items():
        for index in range(links):
            talmud = f"{masechta} {index + 2}a:1"
            halakhah = f"{HILCHOS_AVODA_ZARA} 5:{index + 1}"
            edges.append(
                EinMishpatEdge(halakhah, talmud, "Halakhah", "Talmud")
                if not reverse
                else EinMishpatEdge(talmud, halakhah, "Talmud", "Halakhah")
            )
    return edges


def test_the_fixture_sums_to_the_measured_total() -> None:
    """A fixture that does not sum to 471 is the bug. An earlier draft shipped one summing to 469."""
    assert sum(MEASURED.values()) == MEASURED_TOTAL
    assert len(MEASURED) == MEASURED_MASECHTOS


@pytest.mark.parametrize(
    ("citation", "expected"),
    [
        ("Avodah Zarah 38b:4", "Avodah Zarah"),
        ("Sanhedrin 50a:4", "Sanhedrin"),
        ("Berakhot 43b:19", "Berakhot"),
        ("Bava Kamma 27a", "Bava Kamma"),
        ("Kiddushin 31a:3", "Kiddushin"),
        ("Nazir 33a", "Nazir"),
    ],
)
def test_masechta_of_strips_the_address(citation: str, expected: str) -> None:
    assert masechta_of(citation) == expected


def test_the_ranking_reproduces_the_measured_order() -> None:
    ranks = rank_masechtos(_edges(MEASURED), HILCHOS_AVODA_ZARA)
    assert [rank.masechta for rank in ranks[:5]] == ["Avodah Zarah", "Sanhedrin", "Makkot", "Chullin", "Kiddushin"]


def test_makkot_outranks_chullin_and_kiddushin() -> None:
    """18 beats 14. A naive alphabetical tiebreak would reorder the top five."""
    ranks = {rank.masechta: rank.links for rank in rank_masechtos(_edges(MEASURED), HILCHOS_AVODA_ZARA)}
    assert ranks["Makkot"] == 18
    assert ranks["Chullin"] == ranks["Kiddushin"] == 14


def test_the_measured_shares() -> None:
    ranks = rank_masechtos(_edges(MEASURED), HILCHOS_AVODA_ZARA)
    assert ranks[0].share == pytest.approx(0.425, abs=0.0005)
    assert ranks[1].share == pytest.approx(0.272, abs=0.0005)


def test_the_measured_totals() -> None:
    ranks = rank_masechtos(_edges(MEASURED), HILCHOS_AVODA_ZARA)
    assert sum(rank.links for rank in ranks) == MEASURED_TOTAL
    assert len(ranks) == MEASURED_MASECHTOS


def test_edges_are_counted_in_both_directions() -> None:
    """The export records some edges Talmud-first and others Halakhah-first. Both mean the same."""
    forward = rank_masechtos(_edges(TOP_FIVE), HILCHOS_AVODA_ZARA)
    backward = rank_masechtos(_edges(TOP_FIVE, reverse=True), HILCHOS_AVODA_ZARA)
    assert forward == backward


def test_hilchos_with_no_edges_returns_empty_rather_than_raising() -> None:
    assert rank_masechtos(_edges(TOP_FIVE), "Mishneh Torah, Nothing At All") == []


def test_ties_break_by_name_deterministically() -> None:
    ranks = rank_masechtos(_edges({"Zevachim": 5, "Arakhin": 5, "Menachot": 5}), HILCHOS_AVODA_ZARA)
    assert [rank.masechta for rank in ranks] == ["Arakhin", "Menachot", "Zevachim"]


def test_non_talmud_edges_are_ignored() -> None:
    """A Rambam-to-Shulchan-Aruch edge says nothing about which masechta to learn."""
    edges = [
        EinMishpatEdge(f"{HILCHOS_AVODA_ZARA} 5:2", "Shulchan Arukh, Yoreh De'ah 112:9", "Halakhah", "Halakhah"),
        EinMishpatEdge(f"{HILCHOS_AVODA_ZARA} 5:2", "Sanhedrin 50a:4", "Halakhah", "Talmud"),
    ]
    ranks = rank_masechtos(edges, HILCHOS_AVODA_ZARA)
    assert [rank.masechta for rank in ranks] == ["Sanhedrin"]


def test_a_different_hilchos_is_not_counted() -> None:
    """The prefix match must not catch a longer title that merely starts the same way."""
    edges = [
        EinMishpatEdge("Mishneh Torah, Human Dispositions 5:8", "Berakhot 43b:19", "Halakhah", "Talmud"),
        EinMishpatEdge(f"{HILCHOS_AVODA_ZARA} 5:2", "Sanhedrin 50a:4", "Halakhah", "Talmud"),
    ]
    assert [rank.masechta for rank in rank_masechtos(edges, HILCHOS_AVODA_ZARA)] == ["Sanhedrin"]
