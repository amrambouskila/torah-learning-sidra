from __future__ import annotations

GERESH = "׳"
"""U+05F3 HEBREW PUNCTUATION GERESH — marks a single-letter numeral."""

GERSHAYIM = "״"
"""U+05F4 HEBREW PUNCTUATION GERSHAYIM — sits before the last letter of a multi-letter numeral."""

_HUNDREDS = ((400, "ת"), (300, "ש"), (200, "ר"), (100, "ק"))
_TENS = (
    (90, "צ"),
    (80, "פ"),
    (70, "ע"),
    (60, "ס"),
    (50, "נ"),
    (40, "מ"),
    (30, "ל"),
    (20, "כ"),
    (10, "י"),
)
_UNITS = (
    (9, "ט"),
    (8, "ח"),
    (7, "ז"),
    (6, "ו"),
    (5, "ה"),
    (4, "ד"),
    (3, "ג"),
    (2, "ב"),
    (1, "א"),
)

_TES = "ט"
_VAV = "ו"
_ZAYIN = "ז"

_DIVINE_NAME_EXCEPTIONS = {15: (_TES, _VAV), 16: (_TES, _ZAYIN)}
"""15 and 16 are written tes-vav and tes-zayin rather than yud-heh and yud-vav.

The arithmetic spellings would form a Divine name, so the convention substitutes 9+6 and 9+7.
The rule applies at any magnitude: 115 is kuf-tes-vav.
"""


def to_gematria(number: int) -> str:
    """Render a positive integer as a Hebrew numeral.

    Follows Sefaria's own convention, so computed labels sit consistently beside stored ``heRef``
    strings: a single letter takes a geresh (``א׳``), several letters take gershayim before the
    last (``כ״ח``).
    """
    if number <= 0:
        raise ValueError(f"gematria requires a positive number, got {number}")

    letters: list[str] = []
    remainder = number

    for value, letter in _HUNDREDS:
        while remainder >= value:
            letters.append(letter)
            remainder -= value

    if remainder in _DIVINE_NAME_EXCEPTIONS:
        letters.extend(_DIVINE_NAME_EXCEPTIONS[remainder])
        remainder = 0

    for value, letter in _TENS + _UNITS:
        while remainder >= value:
            letters.append(letter)
            remainder -= value

    if len(letters) == 1:
        return f"{letters[0]}{GERESH}"
    return f"{''.join(letters[:-1])}{GERSHAYIM}{letters[-1]}"
