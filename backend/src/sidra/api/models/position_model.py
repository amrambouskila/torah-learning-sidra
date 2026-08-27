from __future__ import annotations

from pydantic import BaseModel

from sidra.api.sefaria_url import sefaria_url
from sidra.ledger.position import Position


class PositionModel(BaseModel):
    """One resolved place in a track. Hebrew is primary; the transliteration sits beneath it."""

    ref: str
    label_en: str
    label_he: str
    work_ref_title: str
    work_title_he: str
    corpus_ordinal: int
    seq_in_work: int
    sefaria_url: str | None
    """None for Likutei Sichot and The Midrash Says, which are not on Sefaria at all."""

    @classmethod
    def of(cls, position: Position | None) -> PositionModel | None:
        if position is None:
            return None
        return cls(
            ref=position.ref,
            label_en=position.label_en,
            label_he=position.label_he,
            work_ref_title=position.work_ref_title,
            work_title_he=position.work_title_he,
            corpus_ordinal=position.corpus_ordinal,
            seq_in_work=position.seq_in_work,
            sefaria_url=sefaria_url(position.ref) if position.is_linkable else None,
        )
