from __future__ import annotations

from dataclasses import dataclass

import pytest

from sidra.catalog.corpus_ordinal import corpus_ordinal


@dataclass(frozen=True, slots=True)
class _Work:
    ref_title: str
    unit_count: int


# Seder Zeraim as Sefaria reports it: eleven masechtos totalling exactly 75 perakim.
ZERAIM = [
    _Work("Mishnah Berakhot", 9),
    _Work("Mishnah Peah", 8),
    _Work("Mishnah Demai", 7),
    _Work("Mishnah Kilayim", 9),
    _Work("Mishnah Sheviit", 10),
    _Work("Mishnah Terumot", 11),
    _Work("Mishnah Maasrot", 5),
    _Work("Mishnah Maaser Sheni", 5),
    _Work("Mishnah Challah", 4),
    _Work("Mishnah Orlah", 3),
    _Work("Mishnah Bikkurim", 4),
]
MISHNAH = [*ZERAIM, _Work("Mishnah Shabbat", 24), _Work("Mishnah Eruvin", 10)]


def test_seder_zeraim_totals_seventy_five_perakim() -> None:
    assert sum(work.unit_count for work in ZERAIM) == 75


def test_mishnah_shabbat_one_one_is_corpus_ordinal_seventy_six() -> None:
    """Corroborates the real Mishna position: Zeraim is 75 perakim, so Shabbat 1:1 is day 76."""
    assert corpus_ordinal(MISHNAH, "Mishnah Shabbat", 1) == 76


def test_the_first_unit_of_the_first_work_is_ordinal_one() -> None:
    assert corpus_ordinal(MISHNAH, "Mishnah Berakhot", 1) == 1


def test_the_last_unit_of_the_last_work_is_the_corpus_total() -> None:
    total = sum(work.unit_count for work in MISHNAH)
    assert corpus_ordinal(MISHNAH, "Mishnah Eruvin", 10) == total


def test_ordinals_are_contiguous_across_a_work_boundary() -> None:
    assert corpus_ordinal(MISHNAH, "Mishnah Berakhot", 9) == 9
    assert corpus_ordinal(MISHNAH, "Mishnah Peah", 1) == 10


def test_an_unknown_work_raises() -> None:
    with pytest.raises(ValueError, match="not in this corpus"):
        corpus_ordinal(MISHNAH, "Mishnah Yoma", 1)


@pytest.mark.parametrize("seq", [0, -1, 25])
def test_a_seq_beyond_the_work_raises_rather_than_spilling_into_the_next(seq: int) -> None:
    """Without this guard, seq 25 of a 24-perek masechta would silently name the next one."""
    with pytest.raises(ValueError, match="out of range"):
        corpus_ordinal(MISHNAH, "Mishnah Shabbat", seq)
