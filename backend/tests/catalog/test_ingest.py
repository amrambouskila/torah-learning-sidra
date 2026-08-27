from __future__ import annotations

import dataclasses

import pytest

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.corpus_spec import CorpusSpec
from sidra.catalog.granularity import Granularity
from sidra.catalog.ingest import build_drafts
from sidra.catalog.shape import parse_shape
from sidra.catalog.work_draft import WorkDraft


def _node(title: str, he: str, chapters: object, section: str = "Prophets", **extra: object) -> dict[str, object]:
    return {"title": title, "heTitle": he, "section": section, "length": 0, "chapters": chapters, **extra}


NEVIIM_SPEC = CorpusSpec(
    corpus_id="neviim",
    shape_path="Tanakh/Prophets",
    granularity=Granularity.PEREK,
    address_scheme=AddressScheme.FLAT,
)
BAVLI_SPEC = CorpusSpec(
    corpus_id="bavli",
    shape_path="Talmud/Bavli",
    granularity=Granularity.DAF_AMUD,
    address_scheme=AddressScheme.DAF_AMUD,
)


# --------------------------------------------------------------------------- the dataclasses


def test_work_draft_is_frozen() -> None:
    draft = WorkDraft(
        corpus_id="neviim",
        corpus_seq=1,
        index_title="Jeremiah",
        ref_title="Jeremiah",
        title_he="ירמיהו",
        granularity=Granularity.PEREK,
        address_scheme=AddressScheme.FLAT,
        shape=(19, 37),
        labels=None,
        unit_count=2,
        source="sefaria",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        draft.corpus_seq = 2  # type: ignore[misc]


def test_corpus_spec_rejects_an_unknown_corpus_id() -> None:
    with pytest.raises(ValueError, match="unknown corpus_id"):
        CorpusSpec(
            corpus_id="talmud_yerushalmi",
            shape_path="x",
            granularity=Granularity.PEREK,
            address_scheme=AddressScheme.FLAT,
        )


# --------------------------------------------------------------------------- the generic path


def test_a_simple_corpus_produces_one_draft_per_node_in_shape_order() -> None:
    nodes = parse_shape(
        [
            _node("Joshua", "יהושע", [18, 24]),
            _node("Judges", "שופטים", [36, 23, 31]),
            _node("Jeremiah", "ירמיהו", [19]),
        ]
    )
    drafts = build_drafts(nodes, NEVIIM_SPEC)
    assert [d.ref_title for d in drafts] == ["Joshua", "Judges", "Jeremiah"]
    assert [d.corpus_seq for d in drafts] == [1, 2, 3]
    assert [d.unit_count for d in drafts] == [2, 3, 1]
    assert all(d.corpus_id == "neviim" and d.source == "sefaria" for d in drafts)


def test_hebrew_titles_come_through_verbatim_and_stripped() -> None:
    nodes = parse_shape([_node("Jeremiah", "ירמיהו", [19]), _node("Ezekiel", "יחזקאל\n", [28])])
    drafts = build_drafts(nodes, NEVIIM_SPEC)
    assert drafts[0].title_he == "ירמיהו"
    assert drafts[1].title_he == "יחזקאל"


@pytest.mark.parametrize(
    ("name", "length", "empty", "expected"),
    [("avodah-zarah", 152, {0, 1}, 150), ("tamid", 66, set(range(49)), 17), ("nazir", 132, {0, 1, 65}, 129)],
)
def test_bavli_unit_counts_honour_every_measured_trap(name: str, length: int, empty: set[int], expected: int) -> None:
    chapters = [0 if index in empty else 7 for index in range(length)]
    drafts = build_drafts(parse_shape([_node(name, "x", chapters, section="Seder Nezikin")]), BAVLI_SPEC)
    assert drafts[0].unit_count == expected


def test_excluded_sections_produce_no_drafts() -> None:
    """Mishnah's shape carries commentary categories that are not masechtos."""
    spec = dataclasses.replace(
        CorpusSpec(
            corpus_id="mishnah",
            shape_path="Mishnah",
            granularity=Granularity.PEREK,
            address_scheme=AddressScheme.FLAT,
        ),
        exclude_sections=frozenset({"Rishonim on Mishnah", "Modern Commentary on Mishnah"}),
    )
    nodes = parse_shape(
        [
            _node("Mishnah Berakhot", "משנה ברכות", [5, 8], section="Seder Zeraim"),
            _node("Bartenura on Mishnah Berakhot", "ברטנורא", [5], section="Rishonim on Mishnah"),
            _node("English Explanation", "x", [5], section="Modern Commentary on Mishnah"),
        ]
    )
    titles = [d.ref_title for d in build_drafts(nodes, spec)]
    assert titles == ["Mishnah Berakhot"]
    assert "Bartenura on Mishnah Berakhot" not in titles


def test_excluded_titles_produce_no_drafts() -> None:
    """Shulchan Arukh's shape includes an Introduction node that is not a chelek."""
    spec = CorpusSpec(
        corpus_id="shulchan_aruch",
        shape_path="Halakhah/Shulchan Arukh",
        granularity=Granularity.SIMAN,
        address_scheme=AddressScheme.FLAT,
        exclude_titles=frozenset({"Shulchan Arukh, Introduction"}),
    )
    nodes = parse_shape(
        [
            _node("Shulchan Arukh, Orach Chayim", "אורח חיים", [4, 8], section="Shulchan Arukh"),
            _node("Shulchan Arukh, Introduction", "הקדמה", [7], section="Shulchan Arukh"),
        ]
    )
    assert [d.ref_title for d in build_drafts(nodes, spec)] == ["Shulchan Arukh, Orach Chayim"]


# --------------------------------------------------------------------------- the trailing-empty rule


def test_orchot_tzadikim_reports_twenty_nine_gates_but_has_twenty_eight() -> None:
    chapters = [11] * 28 + [0]
    spec = CorpusSpec(
        corpus_id="mussar",
        shape_path="x",
        granularity=Granularity.GATE,
        address_scheme=AddressScheme.FLAT,
    )
    draft = build_drafts(parse_shape([_node("Orchot Tzadikim", "אורחות צדיקים", chapters, section="Musar")]), spec)[0]
    assert draft.unit_count == 28
    assert len(draft.shape) == 28


def test_mesillat_yesharim_reports_twenty_seven_perakim_but_has_twenty_six() -> None:
    chapters = [33] * 26 + [0]
    spec = CorpusSpec(
        corpus_id="mussar",
        shape_path="x",
        granularity=Granularity.PEREK,
        address_scheme=AddressScheme.FLAT,
    )
    draft = build_drafts(parse_shape([_node("Mesillat Yesharim", "מסילת ישרים", chapters, section="Musar")]), spec)[0]
    assert draft.unit_count == 26


def test_interior_empties_are_never_trimmed() -> None:
    """A FLAT entry's position is its identity. Compacting would renumber everything after a gap."""
    draft = build_drafts(parse_shape([_node("X", "x", [5, 0, 7])]), NEVIIM_SPEC)[0]
    assert draft.shape == (5, 0, 7)
    assert draft.unit_count == 3


def test_daf_amud_shapes_keep_their_leading_zeros() -> None:
    """Leading zeros encode that a masechta starts at 2a. Trimming them would shift every daf."""
    chapters = [0, 0, 8, 18]
    draft = build_drafts(parse_shape([_node("X", "x", chapters, section="Seder Nezikin")]), BAVLI_SPEC)[0]
    assert draft.shape == (0, 0, 8, 18)
    assert draft.unit_count == 2


# --------------------------------------------------------------------------- nested and complex


def test_nested_unit_count_is_the_sum_not_the_length() -> None:
    spec = CorpusSpec(
        corpus_id="mishneh_torah",
        shape_path="Halakhah/Mishneh Torah",
        granularity=Granularity.HALAKHAH,
        address_scheme=AddressScheme.NESTED,
    )
    node = _node("Mishneh Torah, Human Dispositions", "הלכות דעות", [7, 7, 3, 23, 13, 10, 8], section="Mishneh Torah")
    draft = build_drafts(parse_shape([node]), spec)[0]
    assert draft.unit_count == 71
    assert len(draft.shape) == 7


def test_a_complex_node_expands_into_its_children() -> None:
    """Even HaEzer is 178 simanim plus two sedarim, not a three-unit work."""
    spec = CorpusSpec(
        corpus_id="shulchan_aruch",
        shape_path="Halakhah/Shulchan Arukh",
        granularity=Granularity.SIMAN,
        address_scheme=AddressScheme.FLAT,
        expand_complex=True,
    )
    payload = [
        {
            "isComplex": True,
            "section": "Shulchan Arukh",
            "length": 180,
            "book": "Shulchan Arukh, Even HaEzer",
            "heBook": "שולחן ערוך, אבן העזר",
            "chapters": [
                {
                    "title": "Shulchan Arukh, Even HaEzer",
                    "heTitle": "אבן העזר",
                    "section": "Shulchan Arukh",
                    "length": 178,
                    "chapters": [3] * 178,
                },
                {
                    "title": "Shulchan Arukh, Even HaEzer, Seder HaGet",
                    "heTitle": "סדר הגט",
                    "section": "Shulchan Arukh",
                    "length": 1,
                    "chapters": [101],
                },
                {
                    "title": "Shulchan Arukh, Even HaEzer, Seder Halitzah",
                    "heTitle": "סדר חליצה",
                    "section": "Shulchan Arukh",
                    "length": 1,
                    "chapters": [57],
                },
            ],
        }
    ]
    drafts = build_drafts(parse_shape(payload), spec)
    assert [d.ref_title for d in drafts] == [
        "Shulchan Arukh, Even HaEzer",
        "Shulchan Arukh, Even HaEzer, Seder HaGet",
        "Shulchan Arukh, Even HaEzer, Seder Halitzah",
    ]
    assert drafts[0].unit_count == 178
    assert drafts[0].title_he == "אבן העזר"


# --------------------------------------------------------------------------- the order override


def test_the_ketuvim_override_reorders_and_renumbers() -> None:
    spec = CorpusSpec(
        corpus_id="ketuvim",
        shape_path="Tanakh/Writings",
        granularity=Granularity.PEREK,
        address_scheme=AddressScheme.FLAT,
        order_override=("Psalms", "Ecclesiastes", "Esther"),
    )
    nodes = parse_shape(
        [
            _node("Psalms", "תהילים", [6], section="Writings"),
            _node("Esther", "אסתר", [22], section="Writings"),
            _node("Ecclesiastes", "קהלת", [18], section="Writings"),
        ]
    )
    drafts = build_drafts(nodes, spec)
    assert [d.ref_title for d in drafts] == ["Psalms", "Ecclesiastes", "Esther"]
    assert [d.corpus_seq for d in drafts] == [1, 2, 3]
    assert drafts[-1].ref_title != "Ecclesiastes"


def test_an_override_naming_a_missing_work_raises() -> None:
    """A Sefaria rename must fail loudly, not silently drop a book."""
    spec = CorpusSpec(
        corpus_id="ketuvim",
        shape_path="x",
        granularity=Granularity.PEREK,
        address_scheme=AddressScheme.FLAT,
        order_override=("Psalms", "Qoheleth"),
    )
    nodes = parse_shape([_node("Psalms", "תהילים", [6], section="Writings")])
    with pytest.raises(ValueError, match="absent from the shape"):
        build_drafts(nodes, spec)


def test_an_override_omitting_a_work_raises() -> None:
    """A book Sefaria adds must not vanish because the override predates it."""
    spec = CorpusSpec(
        corpus_id="ketuvim",
        shape_path="x",
        granularity=Granularity.PEREK,
        address_scheme=AddressScheme.FLAT,
        order_override=("Psalms",),
    )
    nodes = parse_shape(
        [_node("Psalms", "תהילים", [6], section="Writings"), _node("Esther", "אסתר", [22], section="Writings")]
    )
    with pytest.raises(ValueError, match="omits"):
        build_drafts(nodes, spec)


def test_include_section_prefix_keeps_only_matching_sections() -> None:
    """Bavli's shape carries Minor Tractates, Guides and Tziyyun LeNefesh Chayyah beside the sedarim."""
    spec = CorpusSpec(
        corpus_id="bavli",
        shape_path="Talmud/Bavli",
        granularity=Granularity.DAF_AMUD,
        address_scheme=AddressScheme.DAF_AMUD,
        include_section_prefix="Seder ",
    )
    nodes = parse_shape(
        [
            _node("Berakhot", "ברכות", [0, 0, 8], section="Seder Zeraim"),
            _node("Avot D'Rabbi Natan", "אבות דרבי נתן", [0, 0, 5], section="Minor Tractates"),
            _node("Guide", "מדריך", [0, 0, 3], section="Guides"),
        ]
    )
    assert [d.ref_title for d in build_drafts(nodes, spec)] == ["Berakhot"]


def test_a_title_less_node_is_dropped_when_not_expanded() -> None:
    """A complex node with no title and no children has nothing to name a work after."""
    spec = CorpusSpec(
        corpus_id="mussar",
        shape_path="x",
        granularity=Granularity.PEREK,
        address_scheme=AddressScheme.FLAT,
    )
    nodes = parse_shape([{"section": "Musar", "length": 3, "chapters": [1, 2, 3]}])
    assert build_drafts(nodes, spec) == []
