from __future__ import annotations

import pytest

from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.track_kind import TrackKind


@pytest.mark.parametrize("enum_cls", [TrackKind, Period, Category])
def test_every_member_value_is_its_lowercased_name(enum_cls: type) -> None:
    for member in enum_cls:
        assert member.value == member.name.lower()


def test_the_five_track_kinds() -> None:
    assert {m.name for m in TrackKind} == {
        "CORPUS",
        "CURATED_QUEUE",
        "PARSHA_ALIYAH",
        "PARSHA_WEEKLY",
        "OPEN",
    }


def test_the_three_periods() -> None:
    assert {m.name for m in Period} == {"DAY", "WEEK", "NONE"}


def test_the_three_categories() -> None:
    assert {m.name for m in Category} == {"DAILY", "SHABBAT", "CHAVRUSA"}


def test_members_compare_equal_to_their_string_value() -> None:
    assert TrackKind.CORPUS == "corpus"
    assert Period.NONE == "none"
    assert Category.CHAVRUSA == "chavrusa"
