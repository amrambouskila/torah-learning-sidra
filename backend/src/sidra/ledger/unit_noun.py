"""What a track's units are called.

Domain vocabulary, so it lives with the domain rather than in the UI: a badge that reads
"20 amudim behind" is saying something a reader recognises, where "20 units behind" is not.
"""

from __future__ import annotations

from sidra.catalog.granularity import Granularity

NOUNS: dict[Granularity, tuple[str, str]] = {
    Granularity.DAF_AMUD: ("amud", "amudim"),
    Granularity.ALIYAH: ("aliyah", "aliyot"),
    Granularity.PARSHA: ("parsha", "parshiyos"),
    Granularity.PEREK: ("perek", "perakim"),
    Granularity.MISHNAH: ("mishnah", "mishnayos"),
    Granularity.HALAKHAH: ("halachah", "halachos"),
    Granularity.SIMAN: ("siman", "simanim"),
    Granularity.SEIF: ("seif", "seifim"),
    Granularity.OS: ("os", "osiyos"),
    Granularity.GATE: ("shaar", "shearim"),
    Granularity.TORAH_SECTION: ("torah", "torot"),
    Granularity.PARAGRAPH: ("paragraph", "paragraphs"),
}


def unit_nouns(granularity: Granularity) -> tuple[str, str]:
    """The singular and plural forms for a granularity."""
    return NOUNS[granularity]
