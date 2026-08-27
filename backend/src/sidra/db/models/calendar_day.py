from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sidra.db.base import Base


class CalendarDayRow(Base):
    """A snapshotted civil day. The ledger reads these; nothing fetches at request time."""

    __tablename__ = "calendar_day"

    civil_date: Mapped[date] = mapped_column(Date, primary_key=True)
    hebrew_date: Mapped[str] = mapped_column(String(64), nullable=False)
    parsha_en: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    parsha_he: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    is_yom_tov: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
