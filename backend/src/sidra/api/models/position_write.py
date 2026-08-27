from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PositionUpdate(BaseModel):
    """Correct where a track actually stands.

    Say **where you really are**, the same way an advance says where you got to. This endpoint only
    goes backwards: a destination ahead belongs to ``POST /advance``, which records learning rather
    than erasing it.

    ``confirm`` is the seatbelt. Correcting backwards deletes recorded learning and there is no
    undo, so it is refused without an explicit acknowledgement -- the same shape as ``forgive`` on
    the start-date endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    to_ordinal: int | None = Field(default=None, ge=0)
    """Zero means the track has not been opened at all."""

    to_ref: str | None = Field(default=None, min_length=1, max_length=256)
    confirm: bool = False

    @model_validator(mode="after")
    def _one_destination(self) -> PositionUpdate:
        if (self.to_ordinal is None) == (self.to_ref is None):
            raise ValueError("give either to_ordinal or to_ref, not both and not neither")
        return self
