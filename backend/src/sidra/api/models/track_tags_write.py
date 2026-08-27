from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, field_validator


class TrackTagsUpdate(BaseModel):
    """The complete set of tags a track wears, replacing whatever it wore before.

    A whole set rather than add/remove verbs, because the editor is a row of toggles: sending what
    it now shows cannot drift from what he is looking at, and two toggles in quick succession
    cannot interleave into a state neither of them meant.
    """

    model_config = {"extra": "forbid"}

    tag_ids: list[uuid.UUID] = Field(max_length=64)

    @field_validator("tag_ids")
    @classmethod
    def _no_repeats(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("a track wears a tag once; the set holds no repeats")
        return value
