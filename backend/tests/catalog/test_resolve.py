from __future__ import annotations

import pytest

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.bavli_amudim import real_amudim
from sidra.catalog.resolve import unit_at, unit_count

# Every shape below was fetched from the live Sefaria API on 2026-08-24.

JEREMIAH = [
    19,
    37,
    25,
    31,
    31,
    30,
    34,
    23,
    25,
    25,
    23,
    17,
    27,
    22,
    21,
    21,
    27,
    23,
    15,
    18,
    14,
    30,
    40,
    10,
    38,
    24,
    22,
    17,
    32,
    24,
    40,
    44,
    26,
    22,
    19,
    32,
    21,
    28,
    18,
    16,
    18,
    22,
    13,
    30,
    5,
    28,
    7,
    47,
    39,
    46,
    64,
    34,
]
HUMAN_DISPOSITIONS = [7, 7, 3, 23, 13, 10, 8]


def _shape(length: int, empty_indices: set[int]) -> list[int]:
    return [0 if index in empty_indices else 7 for index in range(length)]


AVODAH_ZARAH = _shape(152, {0, 1})
TAMID = _shape(66, set(range(49)))
NAZIR = _shape(132, {0, 1, 65})


def _seq_of_amud(shape: list[int], label: str) -> int:
    """1-based position of an amud among the real ones. NOT the shape index."""
    return real_amudim(shape).index(label) + 1


# --------------------------------------------------------------------------- unit_count


def test_unit_count_flat_is_the_array_length() -> None:
    assert unit_count(AddressScheme.FLAT, JEREMIAH) == 52


def test_unit_count_nested_is_the_array_sum() -> None:
    assert unit_count(AddressScheme.NESTED, HUMAN_DISPOSITIONS) == 71


@pytest.mark.parametrize(
    ("shape", "expected"),
    [(AVODAH_ZARAH, 150), (TAMID, 17), (NAZIR, 129)],
    ids=["avodah-zarah", "tamid", "nazir"],
)
def test_unit_count_daf_amud_counts_non_empty_slots(shape: list[int], expected: int) -> None:
    assert unit_count(AddressScheme.DAF_AMUD, shape) == expected


def test_unit_count_rejects_stored() -> None:
    with pytest.raises(ValueError, match="stored"):
        unit_count(AddressScheme.STORED, [1, 2, 3])


# --------------------------------------------------------------------------- FLAT


def test_flat_resolves_a_perek() -> None:
    unit = unit_at("Jeremiah", AddressScheme.FLAT, JEREMIAH, 44)
    assert unit.seq == 44
    assert unit.addr == ("44",)
    assert unit.ref == "Jeremiah 44"
    assert unit.label_en == "44"
    assert unit.label_he == "מ״ד"
    assert unit.child_count == JEREMIAH[43]


def test_flat_first_and_last() -> None:
    assert unit_at("Jeremiah", AddressScheme.FLAT, JEREMIAH, 1).ref == "Jeremiah 1"
    assert unit_at("Jeremiah", AddressScheme.FLAT, JEREMIAH, 52).ref == "Jeremiah 52"


def test_the_measured_neviim_debt_is_three_perakim() -> None:
    """The real position on 2026-08-24: actual Yirmiyahu 44, scheduled 47, owing 3."""
    actual = unit_at("Jeremiah", AddressScheme.FLAT, JEREMIAH, 44)
    scheduled = unit_at("Jeremiah", AddressScheme.FLAT, JEREMIAH, 47)
    assert scheduled.seq - actual.seq == 3
    assert scheduled.ref == "Jeremiah 47"


# --------------------------------------------------------------------------- NESTED


def test_nested_resolves_the_first_and_last_halacha() -> None:
    assert unit_at("Mishneh Torah, Human Dispositions", AddressScheme.NESTED, HUMAN_DISPOSITIONS, 1).addr == ("1", "1")
    last = unit_at("Mishneh Torah, Human Dispositions", AddressScheme.NESTED, HUMAN_DISPOSITIONS, 71)
    assert last.addr == ("7", "8")


def test_nested_resolves_david_cohens_rambam_position() -> None:
    """Hilchos Deos 5:8. The seq is computed from the array, never hard-coded."""
    seq = sum(HUMAN_DISPOSITIONS[:4]) + 8
    unit = unit_at("Mishneh Torah, Human Dispositions", AddressScheme.NESTED, HUMAN_DISPOSITIONS, seq)
    assert unit.addr == ("5", "8")
    assert unit.ref == "Mishneh Torah, Human Dispositions 5:8"
    assert unit.label_he == "ה׳:ח׳"


def test_nested_crosses_every_chapter_boundary_correctly() -> None:
    seen = [
        unit_at("X", AddressScheme.NESTED, HUMAN_DISPOSITIONS, seq).addr
        for seq in range(1, sum(HUMAN_DISPOSITIONS) + 1)
    ]
    assert seen[0] == ("1", "1")
    assert seen[6] == ("1", "7")
    assert seen[7] == ("2", "1")
    assert len(set(seen)) == 71


def test_nested_child_count_is_none() -> None:
    assert unit_at("X", AddressScheme.NESTED, HUMAN_DISPOSITIONS, 1).child_count is None


# --------------------------------------------------------------------------- DAF_AMUD


def test_daf_amud_resolves_the_real_gemara_position() -> None:
    """seq is the position among real amudim, which is NOT the shape index."""
    seq = _seq_of_amud(AVODAH_ZARAH, "28b")
    unit = unit_at("Avodah Zarah", AddressScheme.DAF_AMUD, AVODAH_ZARAH, seq)
    assert unit.addr == ("28b",)
    assert unit.ref == "Avodah Zarah 28b"
    assert unit.label_he == "כ״ח ע״ב"


def test_the_measured_gemara_debt_is_twenty_amudim() -> None:
    """actual 28b, scheduled 38b. Assert the difference, not the absolute seqs."""
    actual = _seq_of_amud(AVODAH_ZARAH, "28b")
    scheduled = _seq_of_amud(AVODAH_ZARAH, "38b")
    assert scheduled - actual == 20
    assert unit_at("Avodah Zarah", AddressScheme.DAF_AMUD, AVODAH_ZARAH, scheduled).ref == "Avodah Zarah 38b"


def test_seq_is_not_the_shape_index() -> None:
    """For Avodah Zarah the two differ by one, because indices 0 and 1 are empty."""
    from sidra.catalog.amud import amud_label_to_index

    assert amud_label_to_index("28b") == 55
    assert _seq_of_amud(AVODAH_ZARAH, "28b") == 54


def test_daf_amud_first_and_last() -> None:
    assert unit_at("Avodah Zarah", AddressScheme.DAF_AMUD, AVODAH_ZARAH, 1).addr == ("2a",)
    assert unit_at("Avodah Zarah", AddressScheme.DAF_AMUD, AVODAH_ZARAH, 150).addr == ("76b",)


def test_daf_amud_tamid_starts_at_25b() -> None:
    unit = unit_at("Tamid", AddressScheme.DAF_AMUD, TAMID, 1)
    assert unit.addr == ("25b",)
    assert unit.label_he == "כ״ה ע״ב"


def test_daf_amud_nazir_never_resolves_to_its_gap() -> None:
    resolved = {unit_at("Nazir", AddressScheme.DAF_AMUD, NAZIR, seq).addr[0] for seq in range(1, 130)}
    assert "33b" not in resolved
    assert "33a" in resolved
    assert "34a" in resolved


def test_daf_amud_hebrew_label_marks_amud_alef() -> None:
    assert unit_at("Avodah Zarah", AddressScheme.DAF_AMUD, AVODAH_ZARAH, 1).label_he == "ב׳ ע״א"


def test_daf_amud_child_count_is_the_segment_count() -> None:
    assert unit_at("Avodah Zarah", AddressScheme.DAF_AMUD, AVODAH_ZARAH, 1).child_count == 7


# --------------------------------------------------------------------------- bounds and overrides


@pytest.mark.parametrize(
    ("scheme", "shape", "limit"),
    [
        (AddressScheme.FLAT, JEREMIAH, 52),
        (AddressScheme.NESTED, HUMAN_DISPOSITIONS, 71),
        (AddressScheme.DAF_AMUD, AVODAH_ZARAH, 150),
    ],
    ids=["flat", "nested", "daf-amud"],
)
def test_seq_out_of_range_raises(scheme: AddressScheme, shape: list[int], limit: int) -> None:
    with pytest.raises(ValueError, match="out of range"):
        unit_at("X", scheme, shape, 0)
    with pytest.raises(ValueError, match="out of range"):
        unit_at("X", scheme, shape, limit + 1)


def test_stored_scheme_cannot_be_derived() -> None:
    with pytest.raises(ValueError, match="stored"):
        unit_at("Deuteronomy, Ki Tavo", AddressScheme.STORED, [1], 1)


def test_labels_override_the_english_label() -> None:
    """Orchot Tzadikim's gate names are not derivable from a count."""
    gates = ["ON TORAH", "ON HUMILITY", "ON REMORSE"]
    unit = unit_at("Orchot Tzadikim", AddressScheme.FLAT, [11, 9, 11], 3, labels=gates)
    assert unit.label_en == "ON REMORSE"
    assert unit.addr == ("3",)
    assert unit.ref == "Orchot Tzadikim 3"


def test_a_labels_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="labels"):
        unit_at("X", AddressScheme.FLAT, [1, 2, 3], 1, labels=["only-one"])
