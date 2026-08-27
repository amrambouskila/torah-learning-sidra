from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScheduleUpdate(BaseModel):
    """Correct what a track is supposed to be up to.

    Two operands, named rather than chosen silently, because they disagree about the past.
    ``started_on`` moves the day the schedule began counting, which leaves every earlier day
    reading the opening position it was seeded with. A target -- ``to_ordinal`` or ``to_ref`` --
    shifts the opening position itself, which is exact at any delta but restates those days.

    No acknowledgement flag: nothing is destroyed, and sending the previous value back restores it
    exactly.
    """

    model_config = ConfigDict(extra="forbid")

    started_on: date | None = None
    to_ordinal: int | None = Field(default=None, ge=1)
    to_ref: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def _one_correction(self) -> ScheduleUpdate:
        given = [self.started_on, self.to_ordinal, self.to_ref]
        if sum(value is not None for value in given) != 1:
            raise ValueError("give exactly one of started_on, to_ordinal or to_ref")
        return self
