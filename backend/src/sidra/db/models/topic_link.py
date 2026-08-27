from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from sidra.db.base import Base


class TopicLink(Base):
    """One Ein Mishpat edge, or an inferred Tur-bridge edge.

    ``kind`` distinguishes a direct Ein Mishpat citation from one bridged through Tur's siman
    numbering, and ``confidence`` records which of those it is, so the UI never presents an
    inference as a citation.
    """

    __tablename__ = "topic_link"
    __table_args__ = (
        Index("ix_link_from_ref", "from_ref"),
        Index("ix_link_to_ref", "to_ref"),
        Index("ix_link_anchor_group", "anchor_group"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    to_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    from_category: Mapped[str] = mapped_column(String(64), nullable=False)
    to_category: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    anchor_group: Mapped[str] = mapped_column(String(512), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("snapshot.id"), nullable=False)
