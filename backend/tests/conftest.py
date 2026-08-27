from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from sidra.config import get_settings
from sidra.db.base import Base
from sidra.db.engine import create_engine, create_session_factory

TEST_DATABASE = "sidra_test"


def _test_database_url() -> str:
    settings = get_settings()
    return (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{TEST_DATABASE}"
    )


@pytest.fixture(scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Create the schema once for the session and drop it at the end."""
    engine = create_engine(_test_database_url())
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session bound to a transaction that is always rolled back, so tests never see each other."""
    connection = await db_engine.connect()
    transaction = await connection.begin()
    # join_transaction_mode="create_savepoint" makes a session-level rollback unwind only to a
    # SAVEPOINT, leaving the outer transaction for this fixture to roll back. Without it, a test
    # that rolls back (after an expected IntegrityError, say) deassociates the outer transaction
    # and teardown warns.
    session = create_session_factory(db_engine)(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
