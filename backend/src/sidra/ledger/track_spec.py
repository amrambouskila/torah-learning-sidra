"""The parsed form of one entry in ``tracks.yaml``.

Positions arrive as references, not ordinals, so a typo fails the seed instead of quietly placing
a track in the wrong masechta. Resolution happens against the live catalog in ``seed_tracks``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.track_kind import TrackKind


@dataclass(frozen=True, slots=True)
class AliyahPosition:
    """A Chumash position as Amram writes it: a parsha and an aliyah number."""

    parsha: str
    aliyah: int


@dataclass(frozen=True, slots=True)
class TrackSpec:
    """One track, with its position expressed the way the sefer addresses itself."""

    name_en: str
    name_he: str
    category: Category
    kind: TrackKind
    period: Period
    rate: int
    corpus_id: str | None
    work_ref_title: str | None
    starts_on: date | None
    chavrusa: str | None
    tags: tuple[str, ...]

    scheduled_ref: str | None
    """Where the rate says he should be on the file's ``as_of``. Absent means square today."""

    current_ref: str | None
    """Where he actually is. Absent means the track has not been opened."""

    current_aliyah: AliyahPosition | None
    """The Chumash's form of ``current_ref``; the two are mutually exclusive."""

    def __post_init__(self) -> None:
        if self.current_ref is not None and self.current_aliyah is not None:
            raise ValueError(f"{self.name_en}: a track has one current position, not both forms")
        if self.rate < 1:
            raise ValueError(f"{self.name_en}: rate must be at least 1, got {self.rate}")
        if self.kind is TrackKind.CORPUS and self.corpus_id is None:
            raise ValueError(f"{self.name_en}: a corpus track must name a corpus")
        if self.kind is not TrackKind.CORPUS and self.work_ref_title is None:
            raise ValueError(f"{self.name_en}: a {self.kind.value} track must name a work")
        if self.starts_on is not None and self.scheduled_ref is not None:
            raise ValueError(
                f"{self.name_en}: a start date and a scheduled position contradict each other -- "
                "one says nothing is owed before that day, the other says a debt is already carried"
            )
        if self.starts_on is not None and self.period is Period.NONE:
            raise ValueError(f"{self.name_en}: a chavrusa track carries staleness, not a schedule to start")
