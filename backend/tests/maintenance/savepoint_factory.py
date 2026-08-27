"""A session factory a background job can use inside the test harness's rollback transaction.

A job outlives the request that started it, so it opens its own sessions from ``app.state``. In
production that means a fresh connection and a real commit. In a test the whole thing must stay
inside the transaction ``db_session`` rolls back, or one runner's work would leak into every test
that follows it.

So the factory hands back the harness's own session, and maps ``begin()`` onto ``begin_nested()``:
the session is already inside a transaction, and asking it to begin another would raise. This is
the real database throughout -- nothing here is mocked, only re-pointed.
"""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction


class _SavepointSession:
    """The harness's session, with ``begin`` redirected to a savepoint."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __getattr__(self, name: str) -> object:
        return getattr(self._session, name)

    def begin(self) -> AsyncSessionTransaction:
        return self._session.begin_nested()


class _Opened:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> _SavepointSession:
        return _SavepointSession(self._session)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """The harness owns the session's lifetime, so closing it here would break the next call."""


class SavepointFactory:
    """Callable like ``async_sessionmaker``, but bound to the test transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> _Opened:
        return _Opened(self._session)
