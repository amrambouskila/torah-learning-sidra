from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class OrderedWork(Protocol):
    """The slice of ``Work`` this module needs. Keeps the maths testable without a database."""

    ref_title: str
    unit_count: int


def corpus_ordinal(works: Sequence[OrderedWork], ref_title: str, seq: int) -> int:
    """1-based position within a whole corpus, not within one work.

    The sum of every preceding work's ``unit_count`` plus ``seq``. This is what makes the Mishna
    track a single 525-perek stream rather than 63 separate ones, and what puts Mishnah Shabbat 1:1
    at ordinal 76 -- Seder Zeraim being exactly 75 perakim.

    ``works`` must already be in corpus order.
    """
    consumed = 0
    for work in works:
        if work.ref_title == ref_title:
            if not 1 <= seq <= work.unit_count:
                raise ValueError(f"seq {seq} is out of range for {ref_title!r}, which holds {work.unit_count} units")
            return consumed + seq
        consumed += work.unit_count
    raise ValueError(f"{ref_title!r} is not in this corpus")
