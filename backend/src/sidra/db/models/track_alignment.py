from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from sidra.db.base import Base


class TrackAlignment(Base):
    """One track follows another.

    The Gemara track follows Rabbi Jacob's Mishneh Torah track: when he moves to the next hilchos,
    the topic map proposes the matching masechta and Amram confirms it.
    """

    __tablename__ = "track_alignment"
    __table_args__ = (UniqueConstraint("follower_track_id", name="uq_alignment_follower"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    follower_track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("track.id", ondelete="CASCADE"), nullable=False)
    leader_track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("track.id", ondelete="CASCADE"), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="topic_map")
