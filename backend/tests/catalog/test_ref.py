from __future__ import annotations

import pytest

from sidra.catalog.ref import to_ref

ROUND_TRIP_CASES = [
    ("daf+amud", "Avodah Zarah", ["38b"], "Avodah Zarah 38b"),
    ("perek", "Jeremiah", ["44"], "Jeremiah 44"),
    ("mizmor", "Psalms", ["16"], "Psalms 16"),
    ("mishnah", "Mishnah Shabbat", ["1", "1"], "Mishnah Shabbat 1:1"),
    (
        "halakhah",
        "Mishneh Torah, Human Dispositions",
        ["5", "8"],
        "Mishneh Torah, Human Dispositions 5:8",
    ),
    ("siman", "Shulchan Arukh, Orach Chayim", ["1"], "Shulchan Arukh, Orach Chayim 1"),
    ("seif", "Shulchan Arukh, Yoreh De'ah", ["87", "1"], "Shulchan Arukh, Yoreh De'ah 87:1"),
    ("midrash siman", "Bereshit Rabbah", ["3", "5"], "Bereshit Rabbah 3:5"),
    ("os", "Sha'arei Teshuvah", ["1", "29"], "Sha'arei Teshuvah 1:29"),
    ("gate", "Orchot Tzadikim", ["11", "1"], "Orchot Tzadikim 11:1"),
    ("torah section", "Likutei Moharan, Part II", ["1", "1"], "Likutei Moharan, Part II 1:1"),
    (
        "tanya perek",
        "Tanya, Part I; Likkutei Amarim",
        ["1", "1"],
        "Tanya, Part I; Likkutei Amarim 1:1",
    ),
]


@pytest.mark.parametrize(
    ("ref_title", "addr", "expected"),
    [(title, addr, expected) for _, title, addr, expected in ROUND_TRIP_CASES],
    ids=[name for name, _, _, _ in ROUND_TRIP_CASES],
)
def test_to_ref_builds_every_unit_type(ref_title: str, addr: list[str], expected: str) -> None:
    assert to_ref(ref_title, addr) == expected


def test_empty_addr_returns_the_bare_title() -> None:
    """The parsha case — a whole-parsha ref carries no address components."""
    assert to_ref("Deuteronomy, Ki Tavo", []) == "Deuteronomy, Ki Tavo"


def test_a_component_may_contain_a_colon_because_aliyot_carry_ranges() -> None:
    """Rejecting ':' inside a component would make every aliyah unbuildable."""
    assert to_ref("Deuteronomy", ["26:16-26:19"]) == "Deuteronomy 26:16-26:19"


def test_a_semicolon_in_the_title_survives_untouched() -> None:
    """Tanya's Sefaria titles contain a literal semicolon."""
    assert to_ref("Tanya, Part V; Kuntres Acharon", ["9", "1"]) == "Tanya, Part V; Kuntres Acharon 9:1"


def test_addr_components_must_be_strings_not_ints() -> None:
    with pytest.raises(TypeError, match="addr components must be str"):
        to_ref("Jeremiah", [44])  # type: ignore[list-item]
