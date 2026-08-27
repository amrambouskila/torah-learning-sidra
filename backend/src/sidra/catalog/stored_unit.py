from __future__ import annotations

from dataclasses import dataclass

from sidra.catalog.granularity import Granularity


@dataclass(frozen=True, slots=True)
class StoredUnitRow:
    """A unit that must be stored because it cannot be derived from a shape array.

    Aliyot and parshiyos carry Sefaria's own range expansions, which the spec forbids
    synthesizing. ``parent_seq`` is resolved to ``parent_id`` at persist time, after the parent
    rows have been flushed and have ids.
    """

    seq: int
    parent_seq: int | None
    addr: tuple[str, ...]
    addr_types: tuple[str, ...]
    granularity: Granularity
    label_en: str
    label_he: str
    ordinal: int | None
    is_range: bool
    resolved_ref: str | None
    resolved_he_ref: str | None = None
    child_count: int | None = None
