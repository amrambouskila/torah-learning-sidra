"""Infer missing Shulchan Aruch edges through Tur.

Ein Mishpat's coverage is asymmetric: the Bavli-to-Rambam map is near-complete, but the
Bavli-to-Shulchan-Aruch map is genuinely partial. Horayos carries 297 Ein Mishpat links, of which
112 point at Mishneh Torah against 17 across all of Shulchan Aruch. That is structural, not a
defect in the data.

Where an anchor cites Tur but not Shulchan Aruch, a provisional Shulchan Aruch edge is inferred at
siman granularity. Shulchan Aruch follows Tur's siman numbering; across a 23-daf sample every one
of 104 Shulchan Aruch links sat at the identical chelek and siman as its Tur link, with none
unmatched.

Inferred edges are marked ``confidence="inferred"`` and must never be presented as citations.
"""

from __future__ import annotations

import collections
import re
from collections.abc import Iterable

from sidra.alignment.ein_mishpat import EinMishpatEdge

TUR_PREFIX = "Tur, "
SHULCHAN_ARUKH_PREFIX = "Shulchan Arukh, "
HALAKHAH_CATEGORY = "Halakhah"

_TUR_REF = re.compile(r"^Tur, (?P<chelek>.+?) (?P<siman>\d+)$")


def _chelek_and_siman(tur_ref: str) -> tuple[str, str] | None:
    match = _TUR_REF.match(tur_ref.strip())
    if match is None:
        return None
    return match.group("chelek"), match.group("siman")


def _targets_by_anchor(edges: Iterable[EinMishpatEdge]) -> dict[str, list[EinMishpatEdge]]:
    grouped: dict[str, list[EinMishpatEdge]] = collections.defaultdict(list)
    for edge in edges:
        grouped[edge.citation_1].append(edge)
    return grouped


def bridge_via_tur(edges: Iterable[EinMishpatEdge]) -> list[EinMishpatEdge]:
    """Emit a provisional Shulchan Aruch edge wherever an anchor cites Tur but not Shulchan Aruch.

    Never duplicates a direct edge: an anchor that already reaches Shulchan Aruch is left alone.
    The inferred ref is siman-level, since Tur has no seifim to carry across.
    """
    bridged: list[EinMishpatEdge] = []
    for anchor, anchor_edges in _targets_by_anchor(edges).items():
        if any(edge.citation_2.startswith(SHULCHAN_ARUKH_PREFIX) for edge in anchor_edges):
            continue
        for edge in anchor_edges:
            if not edge.citation_2.startswith(TUR_PREFIX):
                continue
            parts = _chelek_and_siman(edge.citation_2)
            if parts is None:
                continue
            chelek, siman = parts
            bridged.append(
                EinMishpatEdge(
                    citation_1=anchor,
                    citation_2=f"{SHULCHAN_ARUKH_PREFIX}{chelek} {siman}",
                    category_1=edge.category_1,
                    category_2=HALAKHAH_CATEGORY,
                )
            )
    return bridged
