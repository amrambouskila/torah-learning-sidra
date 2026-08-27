from __future__ import annotations

import pytest

from sidra.ledger.cycle import align_to, cycle_index, fold
from sidra.ledger.cycle_works import parse_cycle_works

CHUMASH = 378


@pytest.mark.parametrize(
    ("ordinal", "expected"),
    [(1, 1), (377, 377), (378, 378), (379, 1), (380, 2), (756, 378), (757, 1)],
)
def test_the_address_folds_at_the_end_of_the_turn(ordinal: int, expected: int) -> None:
    """378 is the last aliyah of the cycle and 379 is Bereshit again -- the two boundary values
    the whole feature turns on."""
    assert fold(ordinal, CHUMASH) == expected


@pytest.mark.parametrize(
    ("ordinal", "expected"),
    [(1, 1), (378, 1), (379, 2), (756, 2), (757, 3)],
)
def test_the_turn_counts_from_one(ordinal: int, expected: int) -> None:
    assert cycle_index(ordinal, CHUMASH) == expected


@pytest.mark.parametrize("bad", [0, -1])
def test_a_cycle_holds_at_least_one_unit(bad: int) -> None:
    with pytest.raises(ValueError, match="at least one unit"):
        fold(1, bad)
    with pytest.raises(ValueError, match="at least one unit"):
        cycle_index(1, bad)


def test_a_reference_names_a_place_in_the_turn_he_is_standing_in() -> None:
    """He is at Bereshit 7 of the second cycle and types Bereshit 9. It has to mean this year's."""
    assert align_to(9, 385, CHUMASH) == 387


def test_a_correction_backwards_stays_backwards_and_so_stays_a_replay() -> None:
    """The dangerous case. At Ki Tavo Revii, typing Ki Tavo Rishon means "no, I stopped there".
    Lifting it into the next turn would record a year of learning that never happened, and there
    is no undo. It must resolve behind him, where the replay short-circuit catches it."""
    assert align_to(344, 347, CHUMASH) == 344
    assert align_to(344, 347, CHUMASH) < 347


def test_a_reference_on_a_track_never_opened_is_taken_as_written() -> None:
    assert align_to(5, 0, CHUMASH) == 5


def test_a_repeated_work_is_refused() -> None:
    with pytest.raises(ValueError, match="more than once"):
        parse_cycle_works("works:\n  - Likutei Sichot\n  - Likutei Sichot\n")


def test_the_shipped_cycles_file_names_the_four_repeating_works() -> None:
    from sidra.ledger.cycle_works import cycle_ref_titles

    assert cycle_ref_titles() == frozenset(
        {"Parashat HaShavua", "Likutei Sichot", "The Midrash Says", "Covenant and Conversation"}
    )
