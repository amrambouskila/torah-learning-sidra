from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from sidra.alignment.ein_mishpat import EinMishpatEdge
from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.catalog.ingest_aliases import AliasRow
from sidra.catalog.snapshot import FORMAT_VERSION, SnapshotPayload, read_snapshot, write_snapshot
from sidra.catalog.stored_unit import StoredUnitRow
from sidra.catalog.work_draft import WorkDraft

WORKS = (
    WorkDraft(
        corpus_id="bavli",
        corpus_seq=1,
        index_title="Avodah Zarah",
        ref_title="Avodah Zarah",
        title_he="עבודה זרה",
        granularity=Granularity.DAF_AMUD,
        address_scheme=AddressScheme.DAF_AMUD,
        shape=(0, 0, 8, 18),
        labels=None,
        unit_count=2,
        source="sefaria",
    ),
    WorkDraft(
        corpus_id="mussar",
        corpus_seq=1,
        index_title="Orchot Tzadikim",
        ref_title="Orchot Tzadikim",
        title_he="אורחות צדיקים",
        granularity=Granularity.GATE,
        address_scheme=AddressScheme.FLAT,
        shape=(45, 44),
        labels=("ON PRIDE", "ON HUMILITY"),
        unit_count=2,
        source="sefaria",
        labels_he=("שער הגאווה", "שער הענווה"),
    ),
)
UNITS = (
    (
        "Parashat HaShavua",
        StoredUnitRow(
            seq=1,
            parent_seq=None,
            addr=(),
            addr_types=("Parasha",),
            granularity=Granularity.PARSHA,
            label_en="Ki Tavo",
            label_he="כי תבוא",
            ordinal=None,
            is_range=True,
            resolved_ref="Deuteronomy 26:1-29:8",
        ),
    ),
    (
        "Parashat HaShavua",
        StoredUnitRow(
            seq=2,
            parent_seq=1,
            addr=("3",),
            addr_types=("Aliyah",),
            granularity=Granularity.ALIYAH,
            label_en="Shlishi",
            label_he="שלישי",
            ordinal=3,
            is_range=True,
            resolved_ref="Deuteronomy 26:16-26:19",
        ),
    ),
)
ALIASES = (
    AliasRow(ref_title="Avodah Zarah", alias="Mesechet Avoda Zara", lang="en", source="local"),
    AliasRow(ref_title="Avodah Zarah", alias="עבודה זרה", lang="he", source="sefaria"),
)
LINKS = (
    EinMishpatEdge("Avodah Zarah 38b:4", "Mishneh Torah, Forbidden Foods 17:13", "Talmud", "Halakhah"),
    EinMishpatEdge("Avodah Zarah 38b:4", "Tur, Yoreh De'ah 112", "Talmud", "Halakhah"),
)


def _payload() -> SnapshotPayload:
    return SnapshotPayload(
        format_version=FORMAT_VERSION,
        created_at=datetime(2026, 8, 25, 12, 0, tzinfo=UTC),
        sefaria_version="2026-08-25",
        works=WORKS,
        units=UNITS,
        aliases=ALIASES,
        links=LINKS,
    )


def test_a_round_trip_preserves_everything(tmp_path: Path) -> None:
    path = tmp_path / "p1.jsonl"
    write_snapshot(path, _payload())
    assert read_snapshot(path) == _payload()


def test_hebrew_survives_the_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "p1.jsonl"
    write_snapshot(path, _payload())
    restored = read_snapshot(path)
    assert restored.works[0].title_he == "עבודה זרה"
    assert restored.works[1].labels_he == ("שער הגאווה", "שער הענווה")
    assert restored.units[1][1].label_he == "שלישי"


def test_none_valued_fields_survive(tmp_path: Path) -> None:
    path = tmp_path / "p1.jsonl"
    write_snapshot(path, _payload())
    restored = read_snapshot(path)
    assert restored.works[0].labels is None
    assert restored.works[0].labels_he is None
    assert restored.units[0][1].parent_seq is None
    assert restored.units[0][1].ordinal is None


def test_two_writes_are_byte_identical(tmp_path: Path) -> None:
    """A snapshot that differs run to run cannot be committed and diffed."""
    first, second = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    write_snapshot(first, _payload())
    write_snapshot(second, _payload())
    assert first.read_bytes() == second.read_bytes()


def test_created_at_comes_back_timezone_aware(tmp_path: Path) -> None:
    """asyncpg rejects a str for a timestamptz column, so the parse must happen on read."""
    path = tmp_path / "p1.jsonl"
    write_snapshot(path, _payload())
    restored = read_snapshot(path)
    assert isinstance(restored.created_at, datetime)
    assert restored.created_at.tzinfo is not None


def test_a_truncated_file_names_the_line(tmp_path: Path) -> None:
    path = tmp_path / "p1.jsonl"
    write_snapshot(path, _payload())
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([*lines[:3], '{"kind": "work", ']) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=":4:"):
        read_snapshot(path)


def test_a_file_without_a_header_raises(tmp_path: Path) -> None:
    path = tmp_path / "p1.jsonl"
    path.write_text('{"kind":"link","citation_1":"a","citation_2":"b","category_1":"c","category_2":"d"}\n')
    with pytest.raises(ValueError, match="no header"):
        read_snapshot(path)


def test_an_unknown_record_kind_raises(tmp_path: Path) -> None:
    path = tmp_path / "p1.jsonl"
    write_snapshot(path, _payload())
    path.write_text(path.read_text(encoding="utf-8") + '{"kind":"nonsense"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown record kind"):
        read_snapshot(path)


def test_a_future_format_version_raises(tmp_path: Path) -> None:
    """A format change must fail loudly rather than half-load."""
    path = tmp_path / "p1.jsonl"
    write_snapshot(path, _payload())
    text = path.read_text(encoding="utf-8").replace(f'"format_version":{FORMAT_VERSION}', '"format_version":99')
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="format version 99"):
        read_snapshot(path)


def test_blank_lines_are_tolerated(tmp_path: Path) -> None:
    path = tmp_path / "p1.jsonl"
    write_snapshot(path, _payload())
    path.write_text(path.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
    assert read_snapshot(path).works == WORKS


def test_the_parent_directory_is_created(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deeper" / "p1.jsonl"
    write_snapshot(path, _payload())
    assert path.exists()
