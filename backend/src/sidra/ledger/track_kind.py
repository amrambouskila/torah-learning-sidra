from __future__ import annotations

from enum import StrEnum


class TrackKind(StrEnum):
    """Where a track's ordered sequence of units comes from.

    Only ``CURATED_QUEUE`` requires configuration; a ``CORPUS`` track inherits its order, which is
    why Yechezkel following Yirmiyahu is never a decision Amram makes.
    """

    CORPUS = "corpus"
    CURATED_QUEUE = "curated_queue"
    PARSHA_ALIYAH = "parsha_aliyah"
    PARSHA_WEEKLY = "parsha_weekly"
    OPEN = "open"
