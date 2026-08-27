"""The parts of the app the request tests override: the lifespan, the session, the clock, the copy."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.app import VERSION, create_app, lifespan
from sidra.api.deps import get_session, ledger_path, safety_copy_path, today
from sidra.ledger.ledger_file import LEDGER_PATH
from sidra.ledger.safety_copy import SAFETY_COPY_PATH

pytestmark = pytest.mark.integration


async def test_the_lifespan_opens_an_engine_and_disposes_it() -> None:
    app = create_app()
    async with lifespan(app):
        assert app.state.session_factory is not None
        assert app.state.engine is not None
    assert app.state.engine.pool.checkedout() == 0


async def test_the_session_dependency_yields_one_transaction_per_request(db_session: AsyncSession) -> None:
    """Every request gets its own session, opened inside a transaction and committed on the way out."""
    seen: list[object] = []

    class _Factory:
        def __call__(self) -> object:
            return _Ctx()

    class _Ctx:
        async def __aenter__(self) -> object:
            return _Session()

        async def __aexit__(self, *args: object) -> None:
            seen.append("closed")

    class _Session:
        def begin(self) -> _Begin:
            return _Begin()

    class _Begin:
        async def __aenter__(self) -> None:
            seen.append("begun")

        async def __aexit__(self, *args: object) -> None:
            seen.append("committed")

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(session_factory=_Factory())))
    generator: AsyncIterator[object] = get_session(request)  # type: ignore[arg-type]
    session = await anext(generator)
    assert isinstance(session, _Session)
    with pytest.raises(StopAsyncIteration):
        await anext(generator)
    assert seen == ["begun", "committed", "closed"]


def test_the_clock_reads_the_current_civil_date() -> None:
    """One place, so a test can pin the day without patching datetime everywhere."""
    assert today() == datetime.now(UTC).date()
    assert isinstance(today(), date)


def test_the_app_declares_a_version() -> None:
    assert create_app().version == VERSION


def test_the_safety_copy_lands_beside_the_portable_export_but_is_never_it() -> None:
    """Every request test points this at a temp directory, so the real answer is asserted here.

    Writing the pre-correction state into the portable export would leave that file one correction
    stale the moment the correction succeeded, and the launcher imports it into an empty ledger.
    """
    path = safety_copy_path()
    assert path == SAFETY_COPY_PATH
    assert path != LEDGER_PATH
    assert path.parent == LEDGER_PATH.parent


def test_the_export_button_writes_where_the_cli_does() -> None:
    """Overridden in every request test, so the real answer is asserted here."""
    assert ledger_path() == LEDGER_PATH
