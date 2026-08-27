"""Rank the masechtos behind a set of hilchos.

This is what drives the Gemara queue. Rabbi Jacob's Mishneh Torah runs in the Rambam's own order,
and the matching Gemara is pulled across from wherever in Shas it happens to live -- so the queue is
ordered by Mishneh Torah, not by Shas.

The ranking is deliberately a *distribution*, not a single recommendation. Krias Shema is 71%
Berakhot, which is unambiguous; Teshuva's best match is 18% across a long tail. Presenting those
the same way would misrepresent how sure the map is.
"""

from __future__ import annotations

import collections
import re
from collections.abc import Iterable
from typing import NamedTuple

from sidra.alignment.ein_mishpat import EinMishpatEdge

TALMUD_CATEGORY = "Talmud"

_ADDRESS_SUFFIX = re.compile(r"[\s.]\d+[ab]?(:\d+)*$")


class MasechtaRank(NamedTuple):
    masechta: str
    links: int
    share: float


def masechta_of(citation: str) -> str:
    """Strip the address off a Talmud citation. ``Sanhedrin 50a:4`` -> ``Sanhedrin``."""
    return _ADDRESS_SUFFIX.sub("", citation).strip()


def _talmud_side(edge: EinMishpatEdge, hilchos_ref_title: str) -> str | None:
    """Return the Talmud citation of an edge that touches these hilchos, in either direction."""
    prefix = f"{hilchos_ref_title} "
    if edge.citation_1.startswith(prefix) and edge.category_2 == TALMUD_CATEGORY:
        return edge.citation_2
    if edge.citation_2.startswith(prefix) and edge.category_1 == TALMUD_CATEGORY:
        return edge.citation_1
    return None


def rank_masechtos(edges: Iterable[EinMishpatEdge], hilchos_ref_title: str) -> list[MasechtaRank]:
    """Rank masechtos by how many Ein Mishpat links tie them to these hilchos.

    Edges are counted in both directions: the export records some as Talmud to Halakhah and others
    the other way round, and both mean the same thing.

    Ties break by masechta name so the ordering is deterministic.
    """
    counts: collections.Counter[str] = collections.Counter()
    for edge in edges:
        citation = _talmud_side(edge, hilchos_ref_title)
        if citation is not None:
            counts[masechta_of(citation)] += 1

    total = sum(counts.values())
    if total == 0:
        return []
    return [
        MasechtaRank(masechta=masechta, links=links, share=links / total)
        for masechta, links in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
