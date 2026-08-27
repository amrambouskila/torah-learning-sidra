from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.db.base import Base
from sidra.db.engine import create_engine, create_session_factory


def test_base_is_a_declarative_base() -> None:
    assert hasattr(Base, "metadata")
    assert hasattr(Base, "registry")


def test_create_session_factory_returns_an_asyncsession_maker() -> None:
    engine = create_engine("postgresql+asyncpg://u:p@localhost:5524/sidra_test")
    assert create_session_factory(engine).class_ is AsyncSession


@pytest.mark.integration
async def test_the_real_postgres_answers(db_session: AsyncSession) -> None:
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1
