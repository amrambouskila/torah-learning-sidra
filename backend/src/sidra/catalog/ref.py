from __future__ import annotations

from collections.abc import Sequence

ADDR_SEPARATOR = ":"


def to_ref(ref_title: str, addr: Sequence[str]) -> str:
    """Build a Sefaria ref from a title path and its address components.

    An empty ``addr`` returns the bare title -- that is the parsha case. Components may themselves
    contain a colon, because aliyah pointers carry verse ranges such as ``26:16-26:19``.
    """
    for component in addr:
        if not isinstance(component, str):
            raise TypeError(f"addr components must be str, got {type(component).__name__}")
    if not addr:
        return ref_title
    return f"{ref_title} {ADDR_SEPARATOR.join(addr)}"
