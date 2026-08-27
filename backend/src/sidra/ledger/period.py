from __future__ import annotations

from enum import StrEnum


class Period(StrEnum):
    """How often a track's schedule advances.

    ``NONE`` is a chavrusa track: it moves when they meet, so it carries no debt, only staleness.
    """

    DAY = "day"
    WEEK = "week"
    NONE = "none"
