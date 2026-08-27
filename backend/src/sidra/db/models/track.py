from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from sidra.db.base import Base
from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.track_kind import TrackKind


class Track(Base):
    """One line of learning, with a rate and an anchor.

    Everything derived -- the scheduled position, the debt, the projected finish date -- is
    computed per request from these columns plus the catalog. None of it is stored, so derived
    state cannot drift from the ledger.

    ``category`` says where the track appears on screen and is one of three fixed values.
    ``chavrusa_id`` is a separate relation: a track can sit in the Chavrusa category and name a
    chavrusa, but the two are independent columns.
    """

    __tablename__ = "track"
    __table_args__ = (Index("ix_track_category", "category"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    name_he: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[Category] = mapped_column(SAEnum(Category, name="track_category"), nullable=False)
    kind: Mapped[TrackKind] = mapped_column(SAEnum(TrackKind, name="track_kind"), nullable=False)

    # A CORPUS track streams across every work in its corpus; the others name one work at a time.
    corpus_id: Mapped[str | None] = mapped_column(String(32))
    work_ref_title: Mapped[str | None] = mapped_column(String(256))

    rate: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    period: Mapped[Period] = mapped_column(SAEnum(Period, name="track_period"), nullable=False)
    anchor_date: Mapped[date] = mapped_column(Date, nullable=False)
    anchor_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_on: Mapped[date | None] = mapped_column(Date)
    """A track that has not begun accrues no debt; the UI shows "starts in N weeks"."""

    chavrusa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chavrusa.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
