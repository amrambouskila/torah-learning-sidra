from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class AdvanceRequest(BaseModel):
    """Record a movement along a track.

    Say **where you got to**, not how many units that was. Amram knows he finished Human
    Dispositions 5:7; working out that this was three halachos from 5:4, and that 5:7 is unit 289
    of the corpus, is the app's job and not his.

    ``to_ref`` is the reference as the app shows it -- ``5:7`` inside the work he is already in, or
    a whole ref like ``Mishneh Torah, Human Dispositions 5:7``. ``to_ordinal`` remains for the rail,
    where a click already knows the ordinal it means.

    Either one, never both: two answers to the same question can disagree.
    """

    to_ordinal: int | None = Field(default=None, ge=1)
    to_ref: str | None = Field(default=None, min_length=1, max_length=256)
    occurred_on: str | None = None
    note: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _one_destination(self) -> AdvanceRequest:
        if (self.to_ordinal is None) == (self.to_ref is None):
            raise ValueError("give either to_ordinal or to_ref, not both and not neither")
        return self
