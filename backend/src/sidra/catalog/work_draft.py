from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity

SourceKind = Literal["sefaria", "local"]


@dataclass(frozen=True, slots=True)
class WorkDraft:
    """A ``Work`` before it is persisted.

    Ingesters are pure with respect to the database: they return drafts and never touch a session.
    ``persist_works`` is the only code that writes them.
    """

    corpus_id: str
    corpus_seq: int
    index_title: str | None
    ref_title: str
    title_he: str
    granularity: Granularity
    address_scheme: AddressScheme
    shape: tuple[int, ...]
    labels: tuple[str, ...] | None
    unit_count: int
    source: SourceKind
    labels_he: tuple[str, ...] | None = None
