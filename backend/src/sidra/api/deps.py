"""Request-scoped dependencies.

The engine is created once at startup and disposed at shutdown; every request gets its own session
from it, committed on the way out.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sidra.ledger.ledger_file import LEDGER_PATH
from sidra.ledger.safety_copy import SAFETY_COPY_PATH


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session, session.begin():
        yield session


def today() -> date:
    """The current civil date, in one place so tests can pin it."""
    return datetime.now(UTC).date()


def safety_copy_path() -> Path:
    """Where a correction writes the ledger before deleting part of it.

    A dependency rather than a constant read at the call site, so a test can point it at a
    temporary directory instead of writing into the project on every run.
    """
    return SAFETY_COPY_PATH


def ledger_path() -> Path:
    """Where the Maintenance screen's export button writes.

    A dependency for the same reason as ``safety_copy_path``: without it every test that presses
    export would write over the project's own committed ledger.
    """
    return LEDGER_PATH
