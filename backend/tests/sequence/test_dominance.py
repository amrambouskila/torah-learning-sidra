from __future__ import annotations

import pytest

from sidra.sequence.dominance import dominant

# Measured against the live Ein Mishpat data on 2026-08-27: the real counts for the cases Amram
# named. Each is the head of a longer tail, so the *share* here is of the truncated field rather
# than the real one -- which is why these tests assert the ranking rather than the percentage.
FOREIGN_WORSHIP = {"Avodah Zarah": 200, "Sanhedrin": 128, "Makkot": 18, "Chullin": 14, "Nazir": 12}
REPENTANCE = {"Yoma": 19, "Sanhedrin": 16, "Berakhot": 12, "Rosh Hashanah": 10, "Kiddushin": 9}
READING_THE_SHEMA = {"Berakhot": 106, "Shabbat": 9, "Sotah": 5, "Megillah": 4}
HUMAN_DISPOSITIONS = {"Berakhot": 25, "Shabbat": 21, "Arakhin": 13, "Gittin": 13}
TEFILLIN = {"Menachot": 120, "Shabbat": 36, "Yoma": 20, "Bava Batra": 18}
FORBIDDEN_FOODS = {"Chullin": 318, "Avodah Zarah": 288, "Pesachim": 60}


def test_the_masechta_a_section_is_about_is_taken() -> None:
    found = dominant(FOREIGN_WORSHIP)
    assert found is not None
    assert found.masechta == "Avodah Zarah"
    assert found.runner_up == "Sanhedrin"
    assert found.links == 200


def test_a_section_with_no_masechta_of_its_own_yields_none() -> None:
    """The case the whole feature turns on. Teshuvah's leader is Yoma at 1.19x Sanhedrin -- there
    is no masechta of Teshuvah, so the Gemara does not move when the Rambam reaches it."""
    assert dominant(REPENTANCE) is None
    assert dominant(HUMAN_DISPOSITIONS) is None


def test_a_section_split_between_two_masechtos_yields_none() -> None:
    """Hilchos Maachalos Assuros is Chullin 318 against Avodah Zarah 288. Neither owns it, and
    being moved onto either would be the apparatus overstating what it knows."""
    assert dominant(FORBIDDEN_FOODS) is None


@pytest.mark.parametrize(
    ("counts", "expected"),
    [(READING_THE_SHEMA, "Berakhot"), (TEFILLIN, "Menachot")],
)
def test_a_clear_leader_is_taken_however_large_the_field(counts: dict[str, int], expected: str) -> None:
    found = dominant(counts)
    assert found is not None and found.masechta == expected


def test_a_section_with_no_talmudic_citation_at_all_yields_none() -> None:
    """Hilchos Seder Tefillos cites no Gemara whatsoever."""
    assert dominant({}) is None


def test_a_lone_masechta_needs_no_runner_up_to_beat() -> None:
    found = dominant({"Eruvin": 12})
    assert found is not None and found.runner_up is None


def test_a_thin_leader_of_a_wide_field_is_refused() -> None:
    """Twelve percent of a scattered field is not what a section is about, however far ahead."""
    assert dominant({"Bava Kamma": 12, **{f"M{n}": 1 for n in range(88)}}) is None


def test_the_share_is_of_the_whole_field() -> None:
    found = dominant({"Berakhot": 60, "Shabbat": 20, "Yoma": 20})
    assert found is not None
    assert found.share == 0.6
    assert found.links == 60
