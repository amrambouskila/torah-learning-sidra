"""CLI tests.

**These are deliberately synchronous.** Typer's ``CliRunner.invoke`` calls commands that call
``asyncio.run``, and ``asyncio.run`` inside a running loop raises ``RuntimeError``. Under
``asyncio_mode = "auto"`` an ``async def`` test *is* a running loop, so writing these as async tests
fails for a reason that has nothing to do with the code under test.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from sidra.cli import sidra_db

RUNNER = CliRunner()
LAUNCHERS = ("run_torah_sidra.sh", "run_torah_sidra.bat")
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_help_lists_every_command() -> None:
    result = RUNNER.invoke(sidra_db.app, ["--help"])
    assert result.exit_code == 0
    for command in ("init", "seed", "refresh", "verify", "calendar", "seed-tracks", "status"):
        assert command in result.output


def test_seed_reports_what_it_wrote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sidra.db.seed import SeedCounts

    async def fake_seed(session: object, payload: object) -> SeedCounts:
        return SeedCounts(works=250, units=432, aliases=900, links=118805)

    monkeypatch.setattr(sidra_db, "seed_from_snapshot", fake_seed)
    monkeypatch.setattr(sidra_db, "read_snapshot", lambda path: object())
    monkeypatch.setattr(sidra_db, "_session_factory", _fake_factory)

    result = RUNNER.invoke(sidra_db.app, ["seed", "--snapshot", str(tmp_path / "p1.jsonl")])
    assert result.exit_code == 0
    assert "250 works" in result.output
    assert "118805 links" in result.output


def test_verify_exits_non_zero_and_names_the_first_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing(session: object, expected: object) -> list[str]:
        return ["units[bavli]: expected 5349, found 5350"]

    monkeypatch.setattr(sidra_db, "check_catalog", failing)
    monkeypatch.setattr(sidra_db, "load_expected_counts", dict)
    monkeypatch.setattr(sidra_db, "_session_factory", _fake_factory)

    result = RUNNER.invoke(sidra_db.app, ["verify"])
    assert result.exit_code == 1
    assert "units[bavli]" in result.output


def test_verify_succeeds_on_a_clean_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    async def clean(session: object, expected: object) -> list[str]:
        return []

    monkeypatch.setattr(sidra_db, "check_catalog", clean)
    monkeypatch.setattr(sidra_db, "load_expected_counts", dict)
    monkeypatch.setattr(sidra_db, "_session_factory", _fake_factory)

    result = RUNNER.invoke(sidra_db.app, ["verify"])
    assert result.exit_code == 0
    assert "matches every expected count" in result.output


@pytest.mark.parametrize(
    ("catalog_empty", "ledger_empty", "expected"),
    [
        (True, True, "catalog empty, ledger empty"),
        (False, True, "catalog seeded, ledger empty"),
        (False, False, "catalog seeded, ledger seeded"),
    ],
)
def test_status_reports_both_halves(
    monkeypatch: pytest.MonkeyPatch, catalog_empty: bool, ledger_empty: bool, expected: str
) -> None:
    """The launcher seeds the catalog and the ledger separately, so it must see both."""

    async def catalog(session: object) -> bool:
        return catalog_empty

    async def ledger(session: object) -> bool:
        return ledger_empty

    monkeypatch.setattr(sidra_db, "catalog_is_empty", catalog)
    monkeypatch.setattr(sidra_db, "ledger_is_empty", ledger)
    monkeypatch.setattr(sidra_db, "_session_factory", _fake_factory)

    result = RUNNER.invoke(sidra_db.app, ["status"])
    assert result.exit_code == 0
    assert result.output.strip() == expected


def test_calendar_reports_the_span_it_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_index(session: object) -> object:
        return object()

    async def fake_fetch(
        http: object, start: object, end: object, index: object, *, pause_seconds: float
    ) -> list[object]:
        return [object()] * 3

    async def fake_store(session: object, days: object) -> int:
        return 3

    monkeypatch.setattr(sidra_db, "load_parsha_index", fake_index)
    monkeypatch.setattr(sidra_db, "fetch_calendar_range", fake_fetch)
    monkeypatch.setattr(sidra_db, "store_calendar", fake_store)
    monkeypatch.setattr(sidra_db, "_session_factory", _fake_factory)

    result = RUNNER.invoke(sidra_db.app, ["calendar", "--start", "2026-10-06", "--days", "3"])
    assert result.exit_code == 0
    assert "stored 3 calendar days from 2026-10-06 to 2026-10-08" in result.output


def test_seed_tracks_reports_what_it_wrote(monkeypatch: pytest.MonkeyPatch) -> None:
    from sidra.ledger.seed_tracks import TrackSeedCounts

    async def fake_seed(session: object, spec_file: object) -> TrackSeedCounts:
        return TrackSeedCounts(tracks=20, chavrusas=5, tags=1, advances=13, tagged=4)

    monkeypatch.setattr(sidra_db, "seed_tracks", fake_seed)
    monkeypatch.setattr(sidra_db, "load_tracks_file", lambda: object())
    monkeypatch.setattr(sidra_db, "_session_factory", _fake_factory)

    result = RUNNER.invoke(sidra_db.app, ["seed-tracks"])
    assert result.exit_code == 0
    assert "20 tracks" in result.output
    assert "4 tag links" in result.output


def test_the_launchers_seed_and_never_refresh() -> None:
    """Booting into a 656 MB re-crawl would be a bad surprise."""
    for name in LAUNCHERS:
        text = (PROJECT_ROOT / name).read_text(encoding="utf-8")
        assert not re.search(r"sidra[-_]db\s+refresh", text), f"{name} calls refresh on boot"


def test_the_default_snapshot_path_is_inside_the_repo() -> None:
    assert sidra_db.DEFAULT_SNAPSHOT.name == "p1.jsonl"
    assert "snapshots" in sidra_db.DEFAULT_SNAPSHOT.parts


class _FakeSession:
    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def begin(self) -> _FakeSession:
        return self


class _FakeEngine:
    async def dispose(self) -> None:
        return None


def _fake_factory() -> tuple[object, object]:
    return _FakeEngine(), lambda: _FakeSession()


def test_refresh_writes_a_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sidra.catalog.crawl import CrawlResult

    written: dict[str, object] = {}

    async def fake_crawl(client: object, http: object, *, include_links: bool) -> CrawlResult:
        written["include_links"] = include_links
        return CrawlResult(
            payload=SimpleNamespace(works=(1, 2, 3)),  # type: ignore[arg-type]
            unit_count=25000,
            edge_count=118805,
        )

    def fake_write(path: Path, payload: object) -> None:
        written["path"] = path

    monkeypatch.setattr(sidra_db, "crawl_catalog", fake_crawl)
    monkeypatch.setattr(sidra_db, "write_snapshot", fake_write)

    out = tmp_path / "new.jsonl"
    result = RUNNER.invoke(sidra_db.app, ["refresh", "--out", str(out), "--no-links"])
    assert result.exit_code == 0, result.output
    assert written["path"] == out
    assert written["include_links"] is False
    assert "25000 units" in result.output


def test_the_session_factory_builds_an_engine_and_a_maker() -> None:
    """Constructing an engine does not connect, so this is safe without a database."""
    from sqlalchemy.ext.asyncio import AsyncSession

    engine, factory = sidra_db._session_factory()
    assert factory.class_ is AsyncSession  # type: ignore[attr-defined]
    assert engine is not None


def test_init_reports_the_schema_it_created(monkeypatch: pytest.MonkeyPatch) -> None:
    """The schema has to exist before anything can ask the database a question."""
    created: list[object] = []

    class _Connection:
        async def run_sync(self, fn: object) -> None:
            created.append(fn)

    class _Begin:
        async def __aenter__(self) -> _Connection:
            return _Connection()

        async def __aexit__(self, *args: object) -> None:
            return None

    class _Engine:
        def begin(self) -> _Begin:
            return _Begin()

        async def dispose(self) -> None:
            created.append("disposed")

    monkeypatch.setattr(sidra_db, "create_engine", lambda url: _Engine())

    result = RUNNER.invoke(sidra_db.app, ["init"])
    assert result.exit_code == 0
    assert "schema ready" in result.output
    assert "disposed" in created


def test_the_launchers_create_the_schema_before_seeding() -> None:
    """Seeding into a database with no tables fails with a bare UndefinedTableError."""
    for name in LAUNCHERS:
        text = (PROJECT_ROOT / name).read_text(encoding="utf-8")
        assert re.search(r"sidra-db\s+init", text), f"{name} never runs init"
        assert text.index("sidra-db init") < text.index("sidra-db seed"), f"{name} seeds before init"


def test_export_reports_what_it_wrote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    from sidra.ledger.ledger_document import FORMAT_VERSION, LedgerDocument

    async def fake_export(session: object) -> LedgerDocument:
        return LedgerDocument(format_version=FORMAT_VERSION, exported_at=datetime.now(UTC))

    monkeypatch.setattr(sidra_db, "export_ledger", fake_export)
    monkeypatch.setattr(sidra_db, "_session_factory", _fake_factory)

    out = tmp_path / "ledger.json"
    result = RUNNER.invoke(sidra_db.app, ["export", "--out", str(out)])
    assert result.exit_code == 0
    assert "0 tracks" in result.output
    assert out.exists()


def test_import_reports_what_it_wrote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sidra.ledger.transfer import TransferCounts

    async def fake_import(session: object, document: object) -> TransferCounts:
        return TransferCounts(chavrusas=5, tags=1, tracks=20, advances=13, calendar_days=400)

    monkeypatch.setattr(sidra_db, "read_ledger", lambda path: object())
    monkeypatch.setattr(sidra_db, "import_ledger", fake_import)
    monkeypatch.setattr(sidra_db, "_session_factory", _fake_factory)

    result = RUNNER.invoke(sidra_db.app, ["import", "--source", str(tmp_path / "ledger.json")])
    assert result.exit_code == 0
    assert "20 tracks" in result.output
    assert "400 calendar days" in result.output


def test_the_launchers_import_the_ledger_when_one_is_there() -> None:
    """The move that matters: copy the folder, boot, and the history is already back."""
    for name in LAUNCHERS:
        text = (PROJECT_ROOT / name).read_text(encoding="utf-8")
        assert re.search(r"sidra-db\s+import", text), f"{name} never offers to import the ledger"
        assert text.index("sidra-db seed") < text.index("sidra-db import"), f"{name} imports before seeding"
