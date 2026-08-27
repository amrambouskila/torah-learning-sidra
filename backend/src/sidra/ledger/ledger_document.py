"""The portable form of the ledger.

The catalog is reproducible: ``p1.jsonl`` plus ``sidra-db seed`` rebuilds all 27,250 units on any
machine with no network. The **ledger** is not. Every advance Amram records exists nowhere else,
and it lives in a Docker named volume, which does not travel with the project folder. This document
is what makes the folder the whole app: export before copying, import after.

Catalog rows are deliberately absent. Mixing them in would mean a stale export could quietly
overwrite a fresher catalog, and the two have completely different lifetimes.

A strict Pydantic model with ``extra="forbid"``: this is a file read off disk, so it is an
untrusted-input boundary. No pickle, no eval, a size cap, and an unknown field is an error rather
than something silently ignored.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.track_kind import TrackKind

FORMAT_VERSION = 1
MAX_BYTES = 32 * 1024 * 1024
"""A year of calendar plus a decade of advances is well under a megabyte. The cap is a boundary
guard, not a real limit."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChavrusaRecord(_Strict):
    id: uuid.UUID
    name: str = Field(min_length=1, max_length=128)
    notes: str | None = None


class TagRecord(_Strict):
    id: uuid.UUID
    name: str = Field(min_length=1, max_length=64)
    name_he: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=16)


class TrackRecord(_Strict):
    id: uuid.UUID
    name_en: str = Field(min_length=1, max_length=128)
    name_he: str = Field(min_length=1, max_length=128)
    category: Category
    kind: TrackKind
    corpus_id: str | None = Field(default=None, max_length=32)
    work_ref_title: str | None = Field(default=None, max_length=256)
    rate: int = Field(ge=1)
    period: Period
    anchor_date: date
    anchor_ordinal: int = Field(ge=0)
    starts_on: date | None = None
    chavrusa_id: uuid.UUID | None = None
    is_active: bool
    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class AdvanceRecord(_Strict):
    """One movement along a track. These are the rows that exist nowhere but this database."""

    id: uuid.UUID
    track_id: uuid.UUID
    from_ordinal: int = Field(ge=0)
    to_ordinal: int = Field(ge=0)
    unit_count: int = Field(ge=0)
    occurred_at: datetime
    hebrew_date: str = Field(min_length=1, max_length=64)
    note: str | None = None


class CalendarRecord(_Strict):
    """Carried so a new machine does not need ~800 sequential calls to become usable."""

    civil_date: date
    hebrew_date: str = Field(min_length=1, max_length=64)
    parsha_en: list[str] = Field(default_factory=list)
    parsha_he: list[str] = Field(default_factory=list)
    is_yom_tov: bool


class LedgerDocument(_Strict):
    """Everything the catalog cannot rebuild."""

    format_version: int
    exported_at: datetime
    chavrusas: list[ChavrusaRecord] = Field(default_factory=list)
    tags: list[TagRecord] = Field(default_factory=list)
    tracks: list[TrackRecord] = Field(default_factory=list)
    advances: list[AdvanceRecord] = Field(default_factory=list)
    calendar: list[CalendarRecord] = Field(default_factory=list)

    def check_references(self) -> None:
        """Refuse a document whose rows point at each other's absent ids.

        Postgres would refuse it anyway, with a constraint name instead of a sentence. Checking
        here means a hand-edited file says which track is missing.
        """
        if self.format_version != FORMAT_VERSION:
            raise ValueError(f"ledger format version {self.format_version}, this build reads {FORMAT_VERSION}")

        chavrusa_ids = {row.id for row in self.chavrusas}
        tag_ids = {row.id for row in self.tags}
        track_ids = {row.id for row in self.tracks}

        for track in self.tracks:
            if track.chavrusa_id is not None and track.chavrusa_id not in chavrusa_ids:
                raise ValueError(f"track {track.name_en!r} names chavrusa {track.chavrusa_id}, which is not exported")
            for tag_id in track.tag_ids:
                if tag_id not in tag_ids:
                    raise ValueError(f"track {track.name_en!r} names tag {tag_id}, which is not exported")
        for advance in self.advances:
            if advance.track_id not in track_ids:
                raise ValueError(f"advance {advance.id} names track {advance.track_id}, which is not exported")
