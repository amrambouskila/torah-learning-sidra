from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from sidra.db.base import Base


class Advance(Base):
    """One movement along a track.

    This single table is simultaneously the history, the streak data, the pace input for
    projections, and -- for a chavrusa track -- the session log.
    """

    __tablename__ = "advance"
    __table_args__ = (Index("ix_advance_track_occurred", "track_id", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("track.id", ondelete="CASCADE"), nullable=False)
    from_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    to_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hebrew_date: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
