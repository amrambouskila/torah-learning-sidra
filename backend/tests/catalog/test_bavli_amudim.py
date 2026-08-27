from __future__ import annotations

from sidra.catalog.bavli_amudim import real_amudim


def _shape(length: int, empty_indices: set[int]) -> list[int]:
    """A shape `chapters` array of `length` slots, with `empty_indices` carrying no text."""
    return [0 if index in empty_indices else 7 for index in range(length)]


# All three measured against the live Sefaria API on 2026-08-24.
AVODAH_ZARAH = _shape(152, {0, 1})
TAMID = _shape(66, set(range(49)))
NAZIR = _shape(132, {0, 1, 65})


def test_avodah_zarah_has_one_hundred_fifty_real_amudim() -> None:
    amudim = real_amudim(AVODAH_ZARAH)
    assert len(amudim) == 150
    assert amudim[0] == "2a"
    assert amudim[-1] == "76b"


def test_tamid_starts_at_25b_not_2a() -> None:
    """Tamid's first non-empty shape index is 49. Index 51 would be 26b."""
    amudim = real_amudim(TAMID)
    assert amudim[0] == "25b"
    assert amudim[-1] == "33b"
    assert len(amudim) == 17


def test_nazir_omits_its_mid_masechta_gap() -> None:
    """Nazir runs 2a..66b but index 65 (33b) carries no text -- a gap in the middle."""
    amudim = real_amudim(NAZIR)
    assert len(amudim) == 129
    assert amudim[0] == "2a"
    assert amudim[-1] == "66b"
    assert "33b" not in amudim
    assert "33a" in amudim
    assert "34a" in amudim


def test_the_naive_leading_zero_formula_is_wrong_for_nazir() -> None:
    """slots - leading_zeros overcounts Nazir, because its gap is not at the start.

    This is precisely why real_amudim counts non-empty slots instead. Across the whole Bavli the
    naive formula yields 5,350 where the measured count is 5,349.
    """
    leading = next(index for index, count in enumerate(NAZIR) if count)
    assert len(NAZIR) - leading == 130
    assert len(real_amudim(NAZIR)) == 129


def test_an_all_empty_shape_yields_nothing() -> None:
    assert real_amudim([0, 0, 0]) == []


def test_an_empty_shape_yields_nothing() -> None:
    assert real_amudim([]) == []


def test_labels_are_returned_in_shape_order() -> None:
    assert real_amudim(_shape(6, {0, 1})) == ["2a", "2b", "3a", "3b"]
