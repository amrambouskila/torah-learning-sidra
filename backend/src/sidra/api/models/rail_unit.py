from __future__ import annotations

from pydantic import BaseModel


class RailUnit(BaseModel):
    """One unit on a track's rail, with the two markers the UI draws on it."""

    ordinal: int
    ref: str

    work_title_en: str
    """The sefer this unit sits in. A track spanning books repeats its addresses in every one of
    them, so the title is what tells two identical-looking positions apart."""

    work_title_he: str

    label_en: str
    label_he: str
    sefaria_url: str | None
    is_actual: bool
    is_scheduled: bool
