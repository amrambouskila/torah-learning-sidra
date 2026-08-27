"""Folding a cumulative ordinal onto the cycle it repeats."""

from __future__ import annotations


def fold(ordinal: int, cycle_length: int) -> int:
    """Where a cumulative ordinal lands inside one cycle, counting from 1.

    The schedule and the position both count upward forever -- that is what makes debt carry
    across the turn without anything being stored or reset. Only the *address* repeats.
    """
    if cycle_length < 1:
        raise ValueError(f"a cycle holds at least one unit, got {cycle_length}")
    return (ordinal - 1) % cycle_length + 1


def cycle_index(ordinal: int, cycle_length: int) -> int:
    """Which time round this is, counting from 1."""
    if cycle_length < 1:
        raise ValueError(f"a cycle holds at least one unit, got {cycle_length}")
    return (ordinal - 1) // cycle_length + 1


def align_to(base: int, current: int, cycle_length: int) -> int:
    """The occurrence of ``base`` in the turn ``current`` is standing in.

    A reference he types names a place in the cycle, not a lap: "Bereshit 9" means this year's
    Bereshit 9. Aligning it to the current turn keeps a forward reference forward and, just as
    importantly, keeps a *correction* backwards rather than lifting it into a year of learning
    that never happened. Wrapping into the next turn is the picker's job, never a ref's, because a
    bare address cannot distinguish "I got further" from "no, I stopped back there". Both endpoints
    resolve through here and then read the direction themselves: ``POST /advance`` replays a
    backwards ref, ``PUT /position`` corrects to it.
    """
    if current < 1:
        return base
    return base + (cycle_index(current, cycle_length) - 1) * cycle_length
