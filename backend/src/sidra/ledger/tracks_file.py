"""Read ``data/tracks.yaml`` into specs.

Parsing only -- nothing here touches the database or resolves a position. Keeping the two apart
means the file can be validated without a catalog, and a bad enum value names its own track.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.track_kind import TrackKind
from sidra.ledger.track_spec import AliyahPosition, TrackSpec

TRACKS_PATH = Path(__file__).resolve().parents[3] / "data" / "tracks.yaml"


@dataclass(frozen=True, slots=True)
class TagSpec:
    name: str
    name_he: str | None
    color: str | None


@dataclass(frozen=True, slots=True)
class TracksFile:
    """Everything ``tracks.yaml`` declares."""

    as_of: date
    tags: tuple[TagSpec, ...]
    chavrusas: tuple[str, ...]
    tracks: tuple[TrackSpec, ...]


def _aliyah(entry: dict[str, Any] | None) -> AliyahPosition | None:
    return None if entry is None else AliyahPosition(parsha=str(entry["parsha"]), aliyah=int(entry["aliyah"]))


def _track(entry: dict[str, Any]) -> TrackSpec:
    name = str(entry["name_en"])
    try:
        category = Category(entry["category"])
        kind = TrackKind(entry["kind"])
        period = Period(entry["period"])
    except ValueError as error:
        raise ValueError(f"{name}: {error}") from error

    return TrackSpec(
        name_en=name,
        name_he=str(entry["name_he"]),
        category=category,
        kind=kind,
        period=period,
        rate=int(entry.get("rate", 1)),
        corpus_id=entry.get("corpus_id"),
        work_ref_title=entry.get("work_ref_title"),
        starts_on=entry.get("starts_on"),
        chavrusa=entry.get("chavrusa"),
        tags=tuple(entry.get("tags", ())),
        scheduled_ref=entry.get("scheduled_ref"),
        current_ref=entry.get("current_ref"),
        current_aliyah=_aliyah(entry.get("current_aliyah")),
    )


def parse_tracks_file(text: str) -> TracksFile:
    """Parse the YAML. Raises on a duplicate track name or a tag no tag block declares."""
    payload = yaml.safe_load(text)
    tags = tuple(
        TagSpec(name=str(e["name"]), name_he=e.get("name_he"), color=e.get("color")) for e in payload.get("tags", ())
    )
    tracks = tuple(_track(entry) for entry in payload["tracks"])

    names = [track.name_en for track in tracks]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"tracks.yaml declares these track names more than once: {', '.join(duplicates)}")

    declared = {tag.name for tag in tags}
    for track in tracks:
        unknown = sorted(set(track.tags) - declared)
        if unknown:
            raise ValueError(f"{track.name_en}: tag(s) {', '.join(unknown)} are not declared in the tags block")

    chavrusas = tuple(str(entry["name"]) for entry in payload.get("chavrusas", ()))
    for track in tracks:
        if track.chavrusa is not None and track.chavrusa not in chavrusas:
            raise ValueError(f"{track.name_en}: chavrusa {track.chavrusa!r} is not in the chavrusas block")

    return TracksFile(as_of=payload["as_of"], tags=tags, chavrusas=chavrusas, tracks=tracks)


def load_tracks_file(path: Path = TRACKS_PATH) -> TracksFile:
    return parse_tracks_file(path.read_text(encoding="utf-8"))
