from __future__ import annotations

from collections.abc import Sequence

from sidra.catalog.amud import amud_index_to_label


def real_amudim(chapters: Sequence[int]) -> list[str]:
    """Return the labels of every amud that actually carries text, in shape order.

    Counts non-empty slots. It deliberately does **not** compute ``len(chapters) - leading_zeros``:
    Nazir has an empty slot at index 65 (33b) in the middle of a masechta running 2a..66b, so the
    subtraction overcounts by one and the Bavli total comes out 5,350 instead of the measured 5,349.
    """
    return [amud_index_to_label(index) for index, segment_count in enumerate(chapters) if segment_count]
