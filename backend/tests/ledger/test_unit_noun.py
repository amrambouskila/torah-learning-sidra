from __future__ import annotations

import pytest

from sidra.catalog.granularity import Granularity
from sidra.ledger.unit_noun import NOUNS, unit_nouns


@pytest.mark.parametrize("granularity", list(Granularity))
def test_every_granularity_has_a_noun(granularity: Granularity) -> None:
    """A granularity with no noun would render as a KeyError on the Today screen."""
    singular, plural = unit_nouns(granularity)
    assert singular and plural


def test_the_nouns_readers_actually_use() -> None:
    assert unit_nouns(Granularity.DAF_AMUD) == ("amud", "amudim")
    assert unit_nouns(Granularity.PEREK) == ("perek", "perakim")
    assert unit_nouns(Granularity.SIMAN) == ("siman", "simanim")
    assert unit_nouns(Granularity.HALAKHAH) == ("halachah", "halachos")
    assert unit_nouns(Granularity.GATE) == ("shaar", "shearim")


def test_the_table_covers_the_enum_exactly() -> None:
    assert set(NOUNS) == set(Granularity)
