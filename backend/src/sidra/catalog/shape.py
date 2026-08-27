from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ShapeNode:
    """One entry from an ``/api/shape/`` response.

    A complex node describes a work made of sub-works rather than of units: Shulchan Arukh, Even
    HaEzer reports ``length: 180`` whose ``chapters`` are the lengths of three children -- the 178
    simanim, Seder HaGet and Seder Halitzah. Its ``children`` carry those; its ``chapters`` do not
    describe units and must not be treated as though they did.
    """

    title: str | None
    title_he: str
    section: str
    length: int
    chapters: list[int]
    is_complex: bool
    children: tuple[ShapeNode, ...] = field(default=())


def _normalise_chapters(raw: object) -> list[int]:
    """``chapters`` is polymorphic: ``int | list[int] | list[dict]``.

    A bare int means a single section of that length. A list of dicts describes complex child
    nodes, each carrying its own ``length``.
    """
    if raw is None:
        return []
    if isinstance(raw, bool):
        raise TypeError("chapters must not be a bool")
    if isinstance(raw, int):
        return [raw]
    if isinstance(raw, list):
        return [_normalise_entry(entry) for entry in raw]
    raise TypeError(f"unsupported chapters field of type {type(raw).__name__}")


def _normalise_entry(entry: object) -> int:
    """Reduce one ``chapters`` entry to the number of addressable units beneath it.

    A dict is a complex child node carrying its own ``length``. A nested list is a depth-3 node:
    Likutei Moharan reports 286 torot, each an inner list of section lengths padded with trailing
    zeros -- torah 1 is ``[3, 11, 4, 3, 9, 4, 0, 0, 0, 0, 0]``, which is six real sections. Only
    two of its three levels are addressable, so the count of non-empty entries is the unit count.
    """
    if isinstance(entry, dict):
        return int(entry["length"])
    if isinstance(entry, list):
        return sum(1 for inner in entry if inner)
    return int(entry)


def _title(entry: dict[str, Any]) -> str | None:
    """Prefer ``title``, fall back to ``book``.

    Complex nodes omit ``title`` entirely -- Shulchan Arukh, Even HaEzer reports ``title: null``
    with no ``heTitle`` -- but every node carries ``book`` and ``heBook``.
    """
    return (entry.get("title") or entry.get("book") or "").strip() or None


def _title_he(entry: dict[str, Any]) -> str:
    return str(entry.get("heTitle") or entry.get("heBook") or "").strip()


def _parse_node(entry: dict[str, Any]) -> ShapeNode:
    raw_chapters = entry.get("chapters")
    children = (
        tuple(_parse_node(child) for child in raw_chapters if isinstance(child, dict))
        if isinstance(raw_chapters, list)
        else ()
    )
    return ShapeNode(
        title=_title(entry),
        title_he=_title_he(entry),
        section=str(entry.get("section", "")),
        length=int(entry.get("length", 0)),
        chapters=_normalise_chapters(raw_chapters),
        is_complex=bool(entry.get("isComplex", False)),
        children=children,
    )


def parse_shape(payload: list[dict[str, Any]]) -> list[ShapeNode]:
    """Parse an ``/api/shape/`` payload.

    Titles are stripped: Orchot Tzadikim's gate 11 carries a trailing newline in its Hebrew title,
    and an unstripped title would propagate into every label built from it.
    """
    if not isinstance(payload, list):
        raise TypeError(f"shape payload must be a list, got {type(payload).__name__}")
    return [_parse_node(entry) for entry in payload]
