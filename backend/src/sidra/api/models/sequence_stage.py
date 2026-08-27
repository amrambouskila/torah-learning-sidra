from __future__ import annotations

from pydantic import BaseModel


class SequenceWork(BaseModel):
    """One hilchos book inside a stage."""

    ref_title: str
    title_he: str
    halachos: int


class SequenceStage(BaseModel):
    """A run of the code learned against one masechta."""

    masechta_en: str | None
    """None only while the code opens on sections no masechta owns."""

    masechta_he: str | None
    share: float | None
    links: int | None
    runner_up: str | None
    """The masechta that came second, so a close call is visible rather than hidden."""

    works: list[SequenceWork]
    halachos_in_stage: int
    halachos_until: int
    """From where he stands now to this stage's first halachah. Zero for the stage he is in."""

    is_current: bool
    seen_before: bool
    """This masechta already had an earlier stage. The Rambam returns to Berakhot at Hilchos
    Brachos long after Kriyas Shema, and whether to learn it again is his call, not the app's."""
