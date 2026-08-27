from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    """Where a track lives on screen. Exactly one per track, from a fixed set.

    Distinct from tags, which are free-form labels that cut across categories: the ``parsha`` tag
    spans Chumash in DAILY and three works in SHABBAT.
    """

    DAILY = "daily"
    SHABBAT = "shabbat"
    CHAVRUSA = "chavrusa"
