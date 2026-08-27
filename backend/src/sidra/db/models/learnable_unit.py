from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from sidra.catalog.granularity import Granularity
from sidra.db.base import Base


class LearnableUnit(Base):
    """A stored unit, only for works whose units cannot be derived.

    That means aliyot and parshiyos, which carry Sefaria's own range expansions, plus works with
    non-derivable unit names. Roughly 460 rows, not 25,000.
    """

    __tablename__ = "learnable_unit"
    __table_args__ = (
        UniqueConstraint("work_id", "seq", name="uq_unit_work_seq"),
        Index("ix_unit_ref_title", "ref_title"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work.id", ondelete="CASCADE"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("learnable_unit.id", ondelete="CASCADE"))

    ref_title: Mapped[str] = mapped_column(String(256), nullable=False)
    addr: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    addr_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    index_title: Mapped[str | None] = mapped_column(String(256))
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("snapshot.id"), nullable=False)

    is_range: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_ref: Mapped[str | None] = mapped_column(String(512))
    resolved_he_ref: Mapped[str | None] = mapped_column(String(512))
    is_spanning: Mapped[bool | None] = mapped_column(Boolean)

    granularity: Mapped[Granularity] = mapped_column(SAEnum(Granularity, name="granularity"), nullable=False)
    label_en: Mapped[str] = mapped_column(String(256), nullable=False)
    label_he: Mapped[str] = mapped_column(String(256), nullable=False)
    ordinal: Mapped[int | None] = mapped_column(Integer)
    child_count: Mapped[int | None] = mapped_column(Integer)
