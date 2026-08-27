from __future__ import annotations

from enum import StrEnum


class Granularity(StrEnum):
    """What a learnable unit *is*.

    Distinct from ``addr_types``, which says how Sefaria *addresses* it. Conflating the two is the
    most common source of drift across ingesters.
    """

    DAF_AMUD = "daf_amud"
    ALIYAH = "aliyah"
    PARSHA = "parsha"
    PEREK = "perek"
    MISHNAH = "mishnah"
    HALAKHAH = "halakhah"
    SIMAN = "siman"
    SEIF = "seif"
    OS = "os"
    GATE = "gate"
    TORAH_SECTION = "torah_section"
    PARAGRAPH = "paragraph"
