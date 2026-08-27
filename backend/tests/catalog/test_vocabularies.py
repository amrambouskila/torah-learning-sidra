from __future__ import annotations

import pytest

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.corpus import CORPUS_IDS
from sidra.catalog.granularity import Granularity

EXPECTED_GRANULARITIES = {
    "DAF_AMUD",
    "ALIYAH",
    "PARSHA",
    "PEREK",
    "MISHNAH",
    "HALAKHAH",
    "SIMAN",
    "SEIF",
    "OS",
    "GATE",
    "TORAH_SECTION",
    "PARAGRAPH",
}
EXPECTED_SCHEMES = {"FLAT", "NESTED", "DAF_AMUD", "STORED"}
EXPECTED_CORPORA = {
    "torah",
    "neviim",
    "ketuvim",
    "mishnah",
    "bavli",
    "mishneh_torah",
    "shulchan_aruch",
    "mussar",
    "chassidus",
    "midrash",
    "parsha_weekly",
}


@pytest.mark.parametrize("enum_cls", [Granularity, AddressScheme])
def test_every_member_value_is_its_lowercased_name(enum_cls: type) -> None:
    for member in enum_cls:
        assert member.value == member.name.lower()


def test_the_twelve_granularities_are_present() -> None:
    assert {m.name for m in Granularity} == EXPECTED_GRANULARITIES


def test_the_four_address_schemes_are_present() -> None:
    assert {m.name for m in AddressScheme} == EXPECTED_SCHEMES


def test_members_compare_equal_to_their_string_value() -> None:
    assert Granularity.DAF_AMUD == "daf_amud"
    assert AddressScheme.NESTED == "nested"


def test_the_canonical_corpus_vocabulary() -> None:
    assert CORPUS_IDS == frozenset(EXPECTED_CORPORA)


def test_corpus_ids_is_immutable() -> None:
    assert isinstance(CORPUS_IDS, frozenset)
