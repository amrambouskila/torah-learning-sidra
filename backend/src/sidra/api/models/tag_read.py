from __future__ import annotations

import uuid

from pydantic import BaseModel

from sidra.db.models import Tag


class TagRead(BaseModel):
    """A tag, with how many tracks wear it."""

    id: uuid.UUID
    name: str
    name_he: str | None
    color: str | None
    track_count: int

    @classmethod
    def of(cls, tag: Tag, track_count: int) -> TagRead:
        return cls(id=tag.id, name=tag.name, name_he=tag.name_he, color=tag.color, track_count=track_count)
