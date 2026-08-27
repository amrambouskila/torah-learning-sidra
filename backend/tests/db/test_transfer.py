from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.calendar.calendar_day import CalendarDay
from sidra.calendar.store import store_calendar
from sidra.db.models import Advance, CalendarDayRow, Chavrusa, Tag, Track, Work, track_tag
from sidra.ledger.ledger_document import FORMAT_VERSION, LedgerDocument
from sidra.ledger.ledger_file import read_ledger, write_ledger
from sidra.ledger.seed_tracks import actual_ordinal, seed_tracks
from sidra.ledger.tracks_file import parse_tracks_file
from sidra.ledger.transfer import export_ledger, import_ledger
from tests.db.test_seed_tracks import AS_OF, HEBREW_AS_OF, TRACKS_YAML, _catalog

pytestmark = pytest.mark.integration


async def _calendar(session: AsyncSession, days: int = 3) -> None:
    await store_calendar(
        session,
        [
            CalendarDay(
                civil_date=AS_OF + timedelta(days=offset),
                hebrew_date=HEBREW_AS_OF,
                parsha_en=("Ki Tavo",),
                parsha_he=("כי תבוא",),
                is_yom_tov=offset == 1,
            )
            for offset in range(days)
        ],
    )


async def _seeded(session: AsyncSession) -> None:
    await _catalog(session)
    await _calendar(session)
    await seed_tracks(session, parse_tracks_file(TRACKS_YAML))


async def _track(session: AsyncSession, name: str) -> Track:
    return (await session.execute(select(Track).where(Track.name_en == name))).scalar_one()


async def _counts(session: AsyncSession) -> dict[str, int]:
    counts = {}
    for label, model in (("track", Track), ("advance", Advance), ("tag", Tag), ("chavrusa", Chavrusa)):
        counts[label] = int(await session.scalar(select(func.count()).select_from(model)) or 0)
    counts["calendar"] = int(await session.scalar(select(func.count()).select_from(CalendarDayRow)) or 0)
    counts["track_tag"] = int(await session.scalar(select(func.count()).select_from(track_tag)) or 0)
    return counts


# --- export ---------------------------------------------------------------------------------


async def test_the_export_carries_everything_the_catalog_cannot_rebuild(db_session: AsyncSession) -> None:
    await _seeded(db_session)
    document = await export_ledger(db_session)
    assert len(document.tracks) == 4
    assert len(document.advances) == 3
    assert len(document.chavrusas) == 1
    assert len(document.tags) == 1
    assert len(document.calendar) == 3
    assert document.format_version == FORMAT_VERSION


async def test_the_export_carries_no_catalog_rows(db_session: AsyncSession) -> None:
    """A stale export must never be able to overwrite a fresher catalog."""
    await _seeded(db_session)
    fields = set(LedgerDocument.model_fields)
    assert not fields & {"works", "units", "aliases", "links", "snapshots"}


async def test_tag_associations_ride_along_with_their_track(db_session: AsyncSession) -> None:
    await _seeded(db_session)
    document = await export_ledger(db_session)
    tagged = {track.name_en: track.tag_ids for track in document.tracks if track.tag_ids}
    assert set(tagged) == {"Chumash", "Likutei Sichot"}
    assert all(len(ids) == 1 for ids in tagged.values())


async def test_the_export_is_stable_between_runs(db_session: AsyncSession, tmp_path: Path) -> None:
    """Sorted keys and a fixed row order, so a diff reads as what changed rather than a reflow."""
    await _seeded(db_session)
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    document = await export_ledger(db_session)
    write_ledger(first, document)
    write_ledger(second, document)
    assert first.read_bytes() == second.read_bytes()


# --- round trip -----------------------------------------------------------------------------


async def test_a_round_trip_restores_every_row(db_session: AsyncSession, tmp_path: Path) -> None:
    await _seeded(db_session)
    before = await _counts(db_session)
    path = tmp_path / "ledger.json"

    write_ledger(path, await export_ledger(db_session))
    await import_ledger(db_session, read_ledger(path))

    assert await _counts(db_session) == before


async def test_a_round_trip_preserves_the_measured_debt(db_session: AsyncSession, tmp_path: Path) -> None:
    """The point of the whole exercise: the new machine knows he owes three perakim."""
    await _seeded(db_session)
    path = tmp_path / "ledger.json"
    write_ledger(path, await export_ledger(db_session))

    neviim = await _track(db_session, "Neviim")
    anchor, actual = neviim.anchor_ordinal, await actual_ordinal(db_session, neviim)
    await import_ledger(db_session, read_ledger(path))

    restored = await _track(db_session, "Neviim")
    assert restored.anchor_ordinal == anchor
    assert await actual_ordinal(db_session, restored) == actual
    assert anchor - actual == 3


async def test_ids_are_carried_verbatim_so_an_import_is_a_restore(db_session: AsyncSession, tmp_path: Path) -> None:
    """An advance only means anything attached to its own track."""
    await _seeded(db_session)
    path = tmp_path / "ledger.json"
    write_ledger(path, await export_ledger(db_session))
    original = (await db_session.execute(select(Track.id, Track.name_en))).all()

    await import_ledger(db_session, read_ledger(path))
    restored = (await db_session.execute(select(Track.id, Track.name_en))).all()
    assert sorted(original) == sorted(restored)


async def test_a_round_trip_preserves_notes_and_hebrew(db_session: AsyncSession, tmp_path: Path) -> None:
    await _seeded(db_session)
    path = tmp_path / "ledger.json"
    write_ledger(path, await export_ledger(db_session))
    await import_ledger(db_session, read_ledger(path))

    advance = (await db_session.execute(select(Advance).limit(1))).scalar_one()
    assert advance.hebrew_date == HEBREW_AS_OF
    assert advance.note is not None
    tag = (await db_session.execute(select(Tag))).scalar_one()
    assert tag.name_he == "פרשה"


async def test_the_calendar_rides_along_so_a_new_machine_needs_no_network(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    await _seeded(db_session)
    path = tmp_path / "ledger.json"
    write_ledger(path, await export_ledger(db_session))
    await import_ledger(db_session, read_ledger(path))

    rows = (await db_session.execute(select(CalendarDayRow).order_by(CalendarDayRow.civil_date))).scalars().all()
    assert [row.civil_date for row in rows] == [AS_OF + timedelta(days=n) for n in range(3)]
    assert [row.is_yom_tov for row in rows] == [False, True, False]
    assert rows[0].parsha_en == ["Ki Tavo"]


async def test_importing_twice_yields_the_same_rows(db_session: AsyncSession, tmp_path: Path) -> None:
    await _seeded(db_session)
    path = tmp_path / "ledger.json"
    write_ledger(path, await export_ledger(db_session))
    before = await _counts(db_session)

    await import_ledger(db_session, read_ledger(path))
    await import_ledger(db_session, read_ledger(path))
    assert await _counts(db_session) == before


async def test_importing_leaves_the_catalog_alone(db_session: AsyncSession, tmp_path: Path) -> None:
    await _seeded(db_session)
    works = int(await db_session.scalar(select(func.count()).select_from(Work)) or 0)
    path = tmp_path / "ledger.json"
    write_ledger(path, await export_ledger(db_session))

    await import_ledger(db_session, read_ledger(path))
    assert int(await db_session.scalar(select(func.count()).select_from(Work)) or 0) == works


async def test_importing_onto_a_bare_database_works(db_session: AsyncSession, tmp_path: Path) -> None:
    """The move that matters: a fresh machine with a seeded catalog and nothing else."""
    await _seeded(db_session)
    path = tmp_path / "ledger.json"
    document = await export_ledger(db_session)
    write_ledger(path, document)

    from sidra.ledger.seed_tracks import clear_ledger

    await clear_ledger(db_session)
    await db_session.execute(CalendarDayRow.__table__.delete())
    await db_session.flush()

    counts = await import_ledger(db_session, read_ledger(path))
    assert (counts.tracks, counts.advances, counts.calendar_days) == (4, 3, 3)
    assert counts.total == 12


async def test_an_empty_ledger_exports_and_imports_cleanly(db_session: AsyncSession, tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    write_ledger(path, await export_ledger(db_session))
    counts = await import_ledger(db_session, read_ledger(path))
    assert counts.total == 0


# --- the file as an untrusted-input boundary ------------------------------------------------


def _document() -> LedgerDocument:
    return LedgerDocument(format_version=FORMAT_VERSION, exported_at=datetime.now(UTC))


def test_a_missing_file_says_what_to_run(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="run 'sidra-db export' on the old machine"):
        read_ledger(tmp_path / "nothing.json")


def test_a_file_over_the_cap_is_refused_before_it_is_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A strict model refuses bad shapes; only a cap refuses a file too big to hold at all."""
    path = tmp_path / "ledger.json"
    write_ledger(path, _document())
    monkeypatch.setattr("sidra.ledger.ledger_file.MAX_BYTES", 4)
    with pytest.raises(ValueError, match="exceeds the 4-byte ledger cap"):
        read_ledger(path)


def test_an_unknown_field_is_an_error_rather_than_ignored(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    write_ledger(path, _document())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["works"] = [{"ref_title": "smuggled"}]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="not a valid ledger export"):
        read_ledger(path)


def test_malformed_json_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not a valid ledger export"):
        read_ledger(path)


def test_a_future_format_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    write_ledger(path, LedgerDocument(format_version=FORMAT_VERSION + 1, exported_at=datetime.now(UTC)))
    with pytest.raises(ValueError, match=f"this build reads {FORMAT_VERSION}"):
        read_ledger(path)


def test_an_advance_naming_an_absent_track_is_refused() -> None:
    """Postgres would refuse it too, with a constraint name instead of a sentence."""
    document = LedgerDocument.model_validate(
        {
            "format_version": FORMAT_VERSION,
            "exported_at": datetime.now(UTC).isoformat(),
            "advances": [
                {
                    "id": str(uuid.uuid4()),
                    "track_id": str(uuid.uuid4()),
                    "from_ordinal": 1,
                    "to_ordinal": 2,
                    "unit_count": 1,
                    "occurred_at": datetime.now(UTC).isoformat(),
                    "hebrew_date": "x",
                    "note": None,
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="which is not exported"):
        document.check_references()


def test_a_track_naming_an_absent_chavrusa_is_refused() -> None:
    document = LedgerDocument.model_validate(
        {
            "format_version": FORMAT_VERSION,
            "exported_at": datetime.now(UTC).isoformat(),
            "tracks": [
                {
                    "id": str(uuid.uuid4()),
                    "name_en": "Orphan",
                    "name_he": "יתום",
                    "category": "chavrusa",
                    "kind": "curated_queue",
                    "work_ref_title": "Berakhot",
                    "rate": 1,
                    "period": "none",
                    "anchor_date": date(2026, 8, 24).isoformat(),
                    "anchor_ordinal": 1,
                    "chavrusa_id": str(uuid.uuid4()),
                    "is_active": True,
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="names chavrusa"):
        document.check_references()


def test_a_track_naming_an_absent_tag_is_refused() -> None:
    document = LedgerDocument.model_validate(
        {
            "format_version": FORMAT_VERSION,
            "exported_at": datetime.now(UTC).isoformat(),
            "tracks": [
                {
                    "id": str(uuid.uuid4()),
                    "name_en": "Chumash",
                    "name_he": "חומש",
                    "category": "daily",
                    "kind": "parsha_aliyah",
                    "work_ref_title": "Parashat HaShavua",
                    "rate": 1,
                    "period": "day",
                    "anchor_date": date(2026, 8, 24).isoformat(),
                    "anchor_ordinal": 1,
                    "is_active": True,
                    "tag_ids": [str(uuid.uuid4())],
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="names tag"):
        document.check_references()


async def test_importing_a_document_with_bad_references_stops_before_writing(
    db_session: AsyncSession,
) -> None:
    await _seeded(db_session)
    before = await _counts(db_session)
    document = LedgerDocument.model_validate(
        {
            "format_version": FORMAT_VERSION + 1,
            "exported_at": datetime.now(UTC).isoformat(),
        }
    )
    with pytest.raises(ValueError, match="this build reads"):
        await import_ledger(db_session, document)
    assert await _counts(db_session) == before
