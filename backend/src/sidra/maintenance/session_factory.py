"""The type of the thing a background job opens its own sessions with.

A job outlives the request that started it, so it cannot borrow the request's session -- that one
is inside a transaction the dependency closes on the way out.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

SessionFactory = async_sessionmaker[AsyncSession]
