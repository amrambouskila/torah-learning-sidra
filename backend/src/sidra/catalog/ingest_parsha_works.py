"""Ingest the works learned one sicha per parsha week.

Likutei Sichot, The Midrash Says and Covenant and Conversation all advance with the weekly parsha,
so their unit *is* the parsha. They share the 54-parsha spine rather than carrying a structure of
their own, which makes each of them a one-row work with 54 derived units.

Two of the three are not on Sefaria at all. They carry no ref, and the UI shows position without a
deep link -- a normal state, not a degradation.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.catalog.work_draft import WorkDraft

OVERRIDES_DIR = Path(__file__).parent / "overrides"
PARSHIYOS_PER_YEAR = 54


@dataclass(frozen=True, slots=True)
class ParshaWorkSpec:
    ref_title: str
    title_he: str
    source: Literal["sefaria", "local"]
    sefaria_title: str | None


@lru_cache(maxsize=1)
def parsha_work_specs() -> tuple[ParshaWorkSpec, ...]:
    payload = yaml.safe_load((OVERRIDES_DIR / "parsha_works.yaml").read_text(encoding="utf-8"))
    return tuple(
        ParshaWorkSpec(
            ref_title=entry["ref_title"],
            title_he=entry["title_he"],
            source=entry["source"],
            sefaria_title=entry["sefaria_title"],
        )
        for entry in payload["works"]
    )


def build_parsha_work_drafts(
    parsha_names_en: tuple[str, ...],
    parsha_names_he: tuple[str, ...],
) -> list[WorkDraft]:
    """One draft per parsha-weekly work, all sharing the 54-parsha spine."""
    if len(parsha_names_en) != PARSHIYOS_PER_YEAR or len(parsha_names_he) != PARSHIYOS_PER_YEAR:
        raise ValueError(
            f"the parsha spine must hold {PARSHIYOS_PER_YEAR} names, "
            f"got {len(parsha_names_en)} English and {len(parsha_names_he)} Hebrew"
        )
    return [
        WorkDraft(
            corpus_id="parsha_weekly",
            corpus_seq=index,
            index_title=spec.sefaria_title,
            ref_title=spec.ref_title,
            title_he=spec.title_he,
            granularity=Granularity.PARSHA,
            address_scheme=AddressScheme.FLAT,
            shape=(1,) * PARSHIYOS_PER_YEAR,
            labels=parsha_names_en,
            unit_count=PARSHIYOS_PER_YEAR,
            source=spec.source,
            labels_he=parsha_names_he,
        )
        for index, spec in enumerate(parsha_work_specs(), start=1)
    ]
