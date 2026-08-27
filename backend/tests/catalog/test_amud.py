from __future__ import annotations

import pytest

from sidra.catalog.amud import amud_index_to_label, amud_label_to_index

# Measured against the live Sefaria API on 2026-08-24. These are shape-array indices, 0-based.
MEASURED = [
    (2, "2a"),
    (3, "2b"),
    (49, "25b"),
    (55, "28b"),
    (75, "38b"),
    (151, "76b"),
]


@pytest.mark.parametrize(("index", "label"), MEASURED)
def test_index_to_label(index: int, label: str) -> None:
    assert amud_index_to_label(index) == label


@pytest.mark.parametrize(("index", "label"), MEASURED)
def test_label_to_index(index: int, label: str) -> None:
    assert amud_label_to_index(label) == index


def test_the_measured_gemara_debt_is_twenty_amudim() -> None:
    """The real position on 2026-08-24: actual 28b, scheduled 38b, owing 20 amudim."""
    assert amud_label_to_index("38b") - amud_label_to_index("28b") == 20


def test_round_trip_identity_across_a_whole_masechta() -> None:
    for index in range(2, 152):
        assert amud_label_to_index(amud_index_to_label(index)) == index


def test_a_negative_index_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        amud_index_to_label(-1)


@pytest.mark.parametrize("label", ["", "28", "b28", "28c", "28ab", "0a", "-1a", "28 b"])
def test_a_malformed_label_raises(label: str) -> None:
    with pytest.raises(ValueError):
        amud_label_to_index(label)
