from __future__ import annotations

import re

from sidra.constants import AMUDIM_PER_DAF

_LABEL_PATTERN = re.compile(r"(?P<daf>\d+)(?P<side>[ab])")


def amud_index_to_label(index: int) -> str:
    """Convert a Sefaria shape-array index into a daf label.

    Sefaria's Talmud shape arrays are zero-indexed over amudim, so index 0 is daf 1a. Almost every
    masechta starts at 2a, leaving indices 0 and 1 empty.
    """
    if index < 0:
        raise ValueError(f"amud index must be non-negative, got {index}")
    daf = index // AMUDIM_PER_DAF + 1
    side = "b" if index % AMUDIM_PER_DAF else "a"
    return f"{daf}{side}"


def amud_label_to_index(label: str) -> int:
    """Convert a daf label such as ``28b`` into its Sefaria shape-array index."""
    match = _LABEL_PATTERN.fullmatch(label)
    if match is None:
        raise ValueError(f"not a daf label: {label!r}")
    daf = int(match.group("daf"))
    if daf < 1:
        raise ValueError(f"daf must be at least 1, got {daf}")
    side_offset = 1 if match.group("side") == "b" else 0
    return (daf - 1) * AMUDIM_PER_DAF + side_offset
