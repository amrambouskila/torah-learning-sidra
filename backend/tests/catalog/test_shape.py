from __future__ import annotations

import pytest

from sidra.catalog.shape import ShapeNode, parse_shape

SIMPLE = [
    {
        "section": "Prophets",
        "title": "Jeremiah",
        "heTitle": "ירמיהו",
        "length": 52,
        "chapters": [19, 37],
    }
]
INT_CHAPTERS = [
    {
        "section": "Musar",
        "title": "Orchot Tzadikim, Introduction",
        "heTitle": "הקדמה",
        "length": 1,
        "chapters": 24,
    }
]
# Shulchan Arukh, Even HaEzer really does report title: null with isComplex: true.
NULL_TITLE = [
    {
        "section": "Halakhah",
        "title": None,
        "heTitle": "אבן העזר",
        "length": 3,
        "isComplex": True,
        "chapters": [{"title": "Seder HaGet", "length": 101}, {"title": "Seder Halitzah", "length": 57}],
    }
]
# Orchot Tzadikim gate 11 carries a trailing newline in its Hebrew title.
TRAILING_NEWLINE = [
    {
        "section": "Musar",
        "title": "Orchot Tzadikim ",
        "heTitle": "שער האחד-עשר - שער החרטה\n",
        "length": 1,
        "chapters": [11],
    }
]


def test_a_simple_node_parses() -> None:
    assert parse_shape(SIMPLE) == [
        ShapeNode(
            title="Jeremiah",
            title_he="ירמיהו",
            section="Prophets",
            length=52,
            chapters=[19, 37],
            is_complex=False,
        )
    ]


def test_an_int_chapters_field_becomes_a_single_element_list() -> None:
    """Some nodes report chapters as a bare int rather than a list."""
    assert parse_shape(INT_CHAPTERS)[0].chapters == [24]


def test_a_null_title_node_parses_without_raising() -> None:
    node = parse_shape(NULL_TITLE)[0]
    assert node.title is None
    assert node.is_complex is True
    assert node.title_he == "אבן העזר"


def test_dict_chapters_are_reduced_to_their_lengths() -> None:
    assert parse_shape(NULL_TITLE)[0].chapters == [101, 57]


def test_titles_are_stripped_of_whitespace() -> None:
    node = parse_shape(TRAILING_NEWLINE)[0]
    assert node.title == "Orchot Tzadikim"
    assert node.title_he == "שער האחד-עשר - שער החרטה"
    assert not node.title_he.endswith("\n")


def test_a_missing_chapters_field_yields_an_empty_list() -> None:
    assert parse_shape([{"title": "X", "heTitle": "א", "section": "S", "length": 0}])[0].chapters == []


def test_a_non_list_payload_raises() -> None:
    with pytest.raises(TypeError, match="shape payload must be a list"):
        parse_shape({"error": "nope"})  # type: ignore[arg-type]


def test_an_unsupported_chapters_type_raises() -> None:
    with pytest.raises(TypeError, match="chapters"):
        parse_shape([{"title": "X", "heTitle": "א", "section": "S", "length": 1, "chapters": 3.5}])


def test_a_bool_chapters_field_raises() -> None:
    """bool is a subclass of int, so it would silently become [True] without an explicit guard."""
    with pytest.raises(TypeError, match="bool"):
        parse_shape([{"title": "X", "heTitle": "א", "section": "S", "length": 1, "chapters": True}])


# Shulchan Arukh, Even HaEzer as Sefaria really reports it: no title, no heTitle, three children.
EVEN_HAEZER = [
    {
        "isComplex": True,
        "section": "Shulchan Arukh",
        "length": 180,
        "book": "Shulchan Arukh, Even HaEzer",
        "heBook": "שולחן ערוך, אבן העזר",
        "chapters": [
            {
                "title": "Shulchan Arukh, Even HaEzer",
                "heTitle": "שולחן ערוך, אבן העזר",
                "section": "Shulchan Arukh",
                "length": 178,
            },
            {
                "title": "Shulchan Arukh, Even HaEzer, Seder HaGet",
                "heTitle": "שולחן ערוך, אבן העזר, סדר הגט",
                "section": "Shulchan Arukh",
                "length": 1,
            },
            {
                "title": "Shulchan Arukh, Even HaEzer, Seder Halitzah",
                "heTitle": "שולחן ערוך, אבן העזר, סדר חליצה",
                "section": "Shulchan Arukh",
                "length": 1,
            },
        ],
    }
]


def test_a_null_title_falls_back_to_the_book_field() -> None:
    """Even HaEzer reports title: null with no heTitle, but always carries book and heBook."""
    node = parse_shape(EVEN_HAEZER)[0]
    assert node.title == "Shulchan Arukh, Even HaEzer"
    assert node.title_he == "שולחן ערוך, אבן העזר"
    assert node.is_complex is True


def test_a_complex_node_exposes_its_children() -> None:
    """A complex node's chapters are child lengths, not unit counts. The children carry the truth."""
    node = parse_shape(EVEN_HAEZER)[0]
    assert len(node.children) == 3
    assert node.children[0].title == "Shulchan Arukh, Even HaEzer"
    assert node.children[0].length == 178
    assert node.children[1].title.endswith("Seder HaGet")
    assert node.children[2].length == 1


def test_a_simple_node_has_no_children() -> None:
    assert parse_shape(SIMPLE)[0].children == ()


def test_a_nested_list_chapters_field_counts_non_empty_entries() -> None:
    """Likutei Moharan is depth-3: each torah is an inner list of section lengths, zero-padded.

    Torah 1 is [3, 11, 4, 3, 9, 4, 0, 0, 0, 0, 0] -- six real sections, not eleven.
    """
    payload = [
        {
            "title": "Likutei Moharan",
            "heTitle": 'ליקוטי מוהר"ן',
            "section": "Chasidut",
            "length": 3,
            "chapters": [[3, 11, 4, 3, 9, 4, 0, 0, 0, 0, 0], [5, 2, 0], [1]],
        }
    ]
    assert parse_shape(payload)[0].chapters == [6, 2, 1]
