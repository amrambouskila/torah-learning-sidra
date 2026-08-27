from __future__ import annotations

from sidra.constants import (
    AMUDIM_PER_DAF,
    HEBREW_BLOCK_END,
    HEBREW_BLOCK_START,
    SEFARIA_BASE_URL,
)


def test_sefaria_base_url_has_no_trailing_slash() -> None:
    assert SEFARIA_BASE_URL == "https://www.sefaria.org/api"
    assert not SEFARIA_BASE_URL.endswith("/")


def test_amudim_per_daf_is_two() -> None:
    assert AMUDIM_PER_DAF == 2


def test_hebrew_block_bounds_are_the_unicode_hebrew_block() -> None:
    assert HEBREW_BLOCK_START == "֐"
    assert HEBREW_BLOCK_END == "׿"


def test_hebrew_block_contains_alef_and_gershayim() -> None:
    assert HEBREW_BLOCK_START <= "א" <= HEBREW_BLOCK_END
    assert HEBREW_BLOCK_START <= "״" <= HEBREW_BLOCK_END
