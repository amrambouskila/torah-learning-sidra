from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ALIYOT_PER_PARSHA = 7
"""Every parsha's index alt-struct carries exactly seven aliyot.

Maftir is an eighth reading but appears only in ``/api/calendars``, never in the index, so it is
deferred past P1. See the module docstring of ``ingest_parsha``.
"""


@dataclass(frozen=True, slots=True)
class ParashaNode:
    """One parsha as the index alt-struct describes it."""

    title_en: str
    title_he: str
    whole_ref: str
    aliyah_refs: tuple[str, ...]


def parse_parasha_nodes(index_payload: dict[str, Any]) -> list[ParashaNode]:
    """Read ``alts.Parasha.nodes`` from an ``/api/index/`` payload.

    The only parsha parser in the codebase. It reads the ``/api/index/`` form deliberately:
    ``/api/v2/raw/index/`` exposes the same structure under ``alt_structs`` but resolves neither
    ``title`` nor ``heTitle``, so there is no fallback path.
    """
    alts = index_payload.get("alts")
    if not isinstance(alts, dict) or "Parasha" not in alts:
        raise ValueError("index payload carries no alts.Parasha structure")

    nodes = alts["Parasha"].get("nodes", [])
    parsed: list[ParashaNode] = []
    for node in nodes:
        refs = tuple(node.get("refs", ()))
        title = node.get("title") or node.get("sharedTitle") or ""
        if len(refs) != ALIYOT_PER_PARSHA:
            raise ValueError(f"{title!r}: expected {ALIYOT_PER_PARSHA} aliyot, found {len(refs)}")
        parsed.append(
            ParashaNode(
                title_en=title.strip(),
                title_he=str(node.get("heTitle", "")).strip(),
                whole_ref=str(node.get("wholeRef", "")).strip(),
                aliyah_refs=refs,
            )
        )
    return parsed
