from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Table

from sidra.db.base import Base

track_tag = Table(
    "track_tag",
    Base.metadata,
    Column("track_id", ForeignKey("track.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
)
"""Many-to-many between tracks and tags. Cascades on both sides: deleting a tag drops the
association, never the track."""
