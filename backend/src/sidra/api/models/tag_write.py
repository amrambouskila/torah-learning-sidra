from __future__ import annotations

from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    """A new tag. Tags are pure labels: no cadence, no rules, no side effects."""

    name: str = Field(min_length=1, max_length=64)
    name_he: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=16)


class TagUpdate(BaseModel):
    """A change to a tag. Every field is optional; omitted ones are left alone."""

    name: str | None = Field(default=None, min_length=1, max_length=64)
    name_he: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=16)
