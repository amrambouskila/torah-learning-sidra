"""How many days in a row he has recorded something."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta


def longest_run(days: Iterable[date]) -> int:
    """The longest run of consecutive days in the set."""
    ordered = sorted(set(days))
    if not ordered:
        return 0
    best = run = 1
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        run = run + 1 if later == earlier + timedelta(days=1) else 1
        best = max(best, run)
    return best


def current_run(days: Iterable[date], *, on: date) -> int:
    """The run ending today, or yesterday.

    Yesterday counts. A streak that resets at midnight would describe the same ledger differently
    at 23:00 and at 09:00, which is a lie about the ledger rather than a fact about the learning.
    """
    present = set(days)
    tip = on if on in present else on - timedelta(days=1)
    if tip not in present:
        return 0
    run = 0
    while tip in present:
        run += 1
        tip -= timedelta(days=1)
    return run
