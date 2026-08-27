from __future__ import annotations

import pytest

from sidra.calendar.parsha_index import ParshaIndex

# Only the parshiyos these tests actually name. Hebrew is a placeholder in the catalog's own test
# convention -- resolve() passes the catalog's Hebrew straight through, and which Hebrew that is
# belongs to the catalog's tests, not to this one.
INDEX = ParshaIndex.from_names(
    (name, f"he-{name}")
    for name in (
        "Bereshit",
        "Lech Lecha",
        "Nitzavim",
        "Vayeilech",
        "Achrei Mot",
        "Kedoshim",
        "Ki Tavo",
        "Ha'Azinu",
        "Shmini",
    )
)


def test_a_hyphen_inside_one_parshas_name_is_not_a_combined_week() -> None:
    """The live bug. Sefaria writes ``Lech-Lecha``; splitting on the hyphen billed two parshiyos
    for a week that supplies one, and doubled the Chumash's aliyot for that week."""
    assert INDEX.resolve("Lech-Lecha") == (("Lech Lecha",), ("he-Lech Lecha",))


@pytest.mark.parametrize(
    ("display", "expected"),
    [
        ("Nitzavim-Vayeilech", ("Nitzavim", "Vayeilech")),
        ("Achrei Mot-Kedoshim", ("Achrei Mot", "Kedoshim")),
    ],
)
def test_a_genuinely_combined_week_yields_both(display: str, expected: tuple[str, ...]) -> None:
    assert INDEX.resolve(display)[0] == expected


@pytest.mark.parametrize("display", ["Ki Tavo", "  Ki Tavo  ", "Bereshit"])
def test_an_ordinary_week_yields_one(display: str) -> None:
    assert len(INDEX.resolve(display)[0]) == 1


@pytest.mark.parametrize(
    "display",
    [
        "Rosh Hashana I",
        "Sukkot I",
        "Shmini Atzeret",
        "Pesach Shabbat Chol haMoed",
        "Shavuot II",
    ],
)
def test_a_festival_week_supplies_no_sidra(display: str) -> None:
    """The second live bug. These displace the weekly sidra rather than supplying one, so they
    accrue nothing. ``Shmini Atzeret`` is the sharp case: ``Shmini`` is a real parsha and the
    whole label must not be mistaken for it."""
    assert INDEX.resolve(display) == ((), ())


@pytest.mark.parametrize("display", ["Ha'Azinu", "Haazinu", "Ha’Azinu"])
def test_an_apostrophe_is_not_a_separator(display: str) -> None:
    """The catalog writes ``Ha'Azinu``. An apostrophe dropped or curled is the same parsha, but a
    space is not: ``Lech Lecha`` stays two words."""
    assert INDEX.resolve(display)[0] == ("Ha'Azinu",)


def test_a_hyphenated_label_whose_halves_are_not_parshiyos_supplies_nothing() -> None:
    assert INDEX.resolve("Chanukah-Day 3") == ((), ())


def test_an_empty_label_supplies_nothing() -> None:
    assert INDEX.resolve("   ") == ((), ())


def test_the_cycles_final_parsha_is_the_last_one_read() -> None:
    """V'Zot HaBerachah is taken as the last of the cycle rather than by its name, because the
    calendar never says it -- Simchat Torah is not a Shabbos and it is nobody's upcoming sidra."""
    index = ParshaIndex.from_names([("Bereshit", "he-Bereshit"), ("V'Zot HaBerachah", "he-V'Zot")])
    assert index.final == ("V'Zot HaBerachah", "he-V'Zot")
