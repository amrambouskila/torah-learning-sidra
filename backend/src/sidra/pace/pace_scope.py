"""One row the Pace Explorer offers: a body of learning and the unit it is counted in."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Rule = Literal["total", "parents", "children", "aliyot", "daf"]
RULES: frozenset[str] = frozenset({"total", "parents", "children", "aliyot", "daf"})


@dataclass(frozen=True, slots=True)
class PaceScope:
    """A selector over the catalog plus the level to count at.

    A scope is not a corpus. Shas appears twice, by amud and by daf; the Rambam twice, by perek and
    by halachah. And ``corpus_id="mussar"`` would sum six unrelated sefarim into a number nobody
    recognises, so a work-level scope selects by title prefix instead.
    """

    id: str
    scope_en: str
    rule: Rule
    granularity: str
    corpus_ids: tuple[str, ...] = ()
    ref_title_prefix: str | None = None
    exclude_titles: tuple[str, ...] = ()
    """Works the prefix catches that are not units of the body -- Tanya's front matter."""
    unit_singular: str | None = None
    unit_plural: str | None = None
    note: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.rule not in RULES:
            raise ValueError(f"{self.id}: unknown rule {self.rule!r}")
        if self.rule != "aliyot" and not self.corpus_ids and self.ref_title_prefix is None:
            raise ValueError(f"{self.id}: needs a corpus or a title prefix to select anything")
        if (self.unit_singular is None) != (self.unit_plural is None):
            raise ValueError(f"{self.id}: give both noun forms or neither")
