from __future__ import annotations

import pytest

from sidra.catalog.gematria import to_gematria

# Convention matches Sefaria's own heRef strings: a single letter takes a geresh, several letters
# take gershayim before the last. Verified against "שולחן ערוך, אורח חיים א׳:א׳" and "ירמיהו מ״ד".
CASES = [
    (1, "א׳"),
    (2, "ב׳"),
    (5, "ה׳"),
    (9, "ט׳"),
    (10, "י׳"),
    (11, "י״א"),
    (15, "ט״ו"),
    (16, "ט״ז"),
    (17, "י״ז"),
    (26, "כ״ו"),
    (28, "כ״ח"),
    (38, "ל״ח"),
    (44, "מ״ד"),
    (52, "נ״ב"),
    (76, "ע״ו"),
    (100, "ק׳"),
    (115, "קט״ו"),
    (150, "ק״נ"),
    (400, "ת׳"),
    (500, "ת״ק"),
    (999, "תתקצ״ט"),
]


@pytest.mark.parametrize(("number", "expected"), CASES)
def test_to_gematria(number: int, expected: str) -> None:
    assert to_gematria(number) == expected


def test_fifteen_avoids_spelling_a_divine_name() -> None:
    """15 is written tes-vav, not yud-heh, which would spell a Divine name."""
    assert to_gematria(15) == "ט״ו"
    assert to_gematria(15) != "י״ה"


def test_sixteen_avoids_spelling_a_divine_name() -> None:
    """16 is written tes-zayin, not yud-vav."""
    assert to_gematria(16) == "ט״ז"
    assert to_gematria(16) != "י״ו"


def test_the_exception_still_applies_above_one_hundred() -> None:
    assert to_gematria(115) == "קט״ו"
    assert to_gematria(116) == "קט״ז"


def test_single_letters_take_a_geresh_not_gershayim() -> None:
    assert to_gematria(1).endswith("׳")
    assert "״" not in to_gematria(1)


def test_multi_letter_values_take_gershayim_before_the_last_letter() -> None:
    assert to_gematria(28) == "כ" + "״" + "ח"


@pytest.mark.parametrize("number", [0, -1, -100])
def test_non_positive_numbers_raise(number: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        to_gematria(number)


def test_every_output_is_pure_hebrew() -> None:
    """Guards the codepoint rule: only the Hebrew block, nothing else."""
    for number in range(1, 1000):
        assert all("\u0590" <= character <= "\u05ff" for character in to_gematria(number))
