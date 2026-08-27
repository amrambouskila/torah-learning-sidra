"""Read ``data/pace_scopes.yaml``. Parsing only; nothing here touches the database."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml

from sidra.pace.pace_scope import PaceScope, Rule

SCOPES_PATH = Path(__file__).resolve().parents[3] / "data" / "pace_scopes.yaml"


def parse_scopes(text: str) -> tuple[PaceScope, ...]:
    payload = yaml.safe_load(text)
    scopes = tuple(
        PaceScope(
            id=str(entry["id"]),
            scope_en=str(entry["scope_en"]),
            rule=cast("Rule", str(entry["rule"])),
            granularity=str(entry["granularity"]),
            corpus_ids=tuple(entry.get("corpus_ids", ())),
            ref_title_prefix=entry.get("ref_title_prefix"),
            exclude_titles=tuple(entry.get("exclude_titles", ())),
            unit_singular=entry.get("unit_singular"),
            unit_plural=entry.get("unit_plural"),
            note=_squash(entry.get("note")),
        )
        for entry in cast("list[dict[str, Any]]", payload["scopes"])
    )
    ids = [scope.id for scope in scopes]
    duplicates = sorted({name for name in ids if ids.count(name) > 1})
    if duplicates:
        raise ValueError(f"pace_scopes.yaml declares these ids more than once: {', '.join(duplicates)}")
    return scopes


def _squash(note: object) -> str | None:
    """YAML folded scalars keep a trailing newline; a note is one sentence on one line."""
    return None if note is None else " ".join(str(note).split())


@lru_cache(maxsize=1)
def load_scopes(path: Path = SCOPES_PATH) -> tuple[PaceScope, ...]:
    return parse_scopes(path.read_text(encoding="utf-8"))
