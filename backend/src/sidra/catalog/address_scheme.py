from __future__ import annotations

from enum import StrEnum


class AddressScheme(StrEnum):
    """How a position integer maps onto an address within a work.

    Units are derived rather than stored, so a work carries Sefaria's shape array and declares
    which of these applies. ``STORED`` is the exception: works whose units carry data that cannot
    be computed (aliyot with Sefaria's own range expansions, gates with non-derivable names).
    """

    FLAT = "flat"
    NESTED = "nested"
    DAF_AMUD = "daf_amud"
    STORED = "stored"
