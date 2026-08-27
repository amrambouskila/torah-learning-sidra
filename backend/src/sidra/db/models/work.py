from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.db.base import Base


class Work(Base):
    """One sefer or one book, carrying Sefaria's own shape array.

    Units are derived from ``shape`` via ``unit_at`` rather than stored, so Avodah Zarah is one row
    and 152 integers instead of 150 rows.
    """

    __tablename__ = "work"
    __table_args__ = (
        UniqueConstraint("corpus_id", "corpus_seq", name="uq_work_corpus_position"),
        Index("ix_work_ref_title", "ref_title"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corpus_id: Mapped[str] = mapped_column(String(32), nullable=False)
    corpus_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    index_title: Mapped[str | None] = mapped_column(String(256))
    ref_title: Mapped[str] = mapped_column(String(256), nullable=False)
    title_he: Mapped[str] = mapped_column(String(256), nullable=False)
    granularity: Mapped[Granularity] = mapped_column(SAEnum(Granularity, name="granularity"), nullable=False)
    address_scheme: Mapped[AddressScheme] = mapped_column(SAEnum(AddressScheme, name="address_scheme"), nullable=False)
    shape: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    labels: Mapped[list[str] | None] = mapped_column(JSONB)
    labels_he: Mapped[list[str] | None] = mapped_column(JSONB)
    unit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("snapshot.id"), nullable=False)
