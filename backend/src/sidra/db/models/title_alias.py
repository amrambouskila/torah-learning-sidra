from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from sidra.db.base import Base


class TitleAlias(Base):
    """An alternative spelling for a work, either Sefaria's own or one of Amram's."""

    __tablename__ = "title_alias"
    __table_args__ = (Index("ix_alias_alias", "alias"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(String(256), nullable=False)
    lang: Mapped[str] = mapped_column(String(2), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
