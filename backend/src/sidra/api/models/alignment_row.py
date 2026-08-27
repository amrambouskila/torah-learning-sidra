from __future__ import annotations

from pydantic import BaseModel


class AlignmentRow(BaseModel):
    """One masechta tied to a set of hilchos by the Ein Mishpat apparatus.

    ``share`` is what makes this a distribution rather than a recommendation: Krias Shema is 71%
    Berakhot, which is unambiguous; Teshuva's best match is 18% across a long tail. Presenting
    those the same way would misrepresent how sure the map is.
    """

    masechta: str
    links: int
    share: float
    is_inferred: bool
    """True when the edges come through Tur's siman numbering rather than a direct citation."""
