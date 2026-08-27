from __future__ import annotations

from dataclasses import dataclass, field

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.corpus import CORPUS_IDS
from sidra.catalog.granularity import Granularity


@dataclass(frozen=True, slots=True)
class CorpusSpec:
    """How to turn one ``/api/shape/`` response into a corpus of works.

    Seven corpora share one ingester because, once units are derived, ingestion is the same job
    everywhere: fetch a shape, drop what does not belong, put the rest in order, keep each node's
    array.
    """

    corpus_id: str
    shape_path: str
    granularity: Granularity
    address_scheme: AddressScheme
    include_section_prefix: str | None = None
    exclude_sections: frozenset[str] = field(default=frozenset())
    exclude_titles: frozenset[str] = field(default=frozenset())
    order_override: tuple[str, ...] | None = None
    expand_complex: bool = False

    def __post_init__(self) -> None:
        if self.corpus_id not in CORPUS_IDS:
            raise ValueError(f"unknown corpus_id {self.corpus_id!r}; expected one of {sorted(CORPUS_IDS)}")
