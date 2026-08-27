"""Build the title-alias layer.

Two sources. Sefaria ships its own spellings under ``schema.titles`` on the v2 raw index -- the
only endpoint that carries them, which is why ``SefariaClient`` has ``raw_index``. And a local file
maps Amram's own spellings onto the canonical ``ref_title``, because Sefaria's English titles for
Mishneh Torah are translations rather than transliterations: "Hilchos Daos" is "Mishneh Torah,
Human Dispositions".
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

OVERRIDES_DIR = Path(__file__).parent / "overrides"

AliasSource = Literal["sefaria", "local"]


@dataclass(frozen=True, slots=True)
class AliasRow:
    ref_title: str
    alias: str
    lang: Literal["en", "he"]
    source: AliasSource


@lru_cache(maxsize=1)
def local_aliases() -> tuple[tuple[str, str], ...]:
    """(alias, canonical ref_title) pairs for Amram's own spellings."""
    payload = yaml.safe_load((OVERRIDES_DIR / "local_aliases.yaml").read_text(encoding="utf-8"))
    return tuple((alias, ref_title) for alias, ref_title in payload["aliases"].items())


def _lang_of(entry: dict[str, object]) -> Literal["en", "he"]:
    return "he" if str(entry.get("lang", "en")) == "he" else "en"


def sefaria_aliases(ref_title: str, raw_index_payload: dict[str, object]) -> list[AliasRow]:
    """Harvest ``schema.titles`` from a v2 raw index payload."""
    schema = raw_index_payload.get("schema")
    titles = schema.get("titles", []) if isinstance(schema, dict) else []
    rows: list[AliasRow] = []
    seen: set[tuple[str, str]] = set()
    for entry in titles:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("text", "")).strip()
        if not text:
            continue
        lang = _lang_of(entry)
        if (text, lang) in seen:
            continue
        seen.add((text, lang))
        rows.append(AliasRow(ref_title=ref_title, alias=text, lang=lang, source="sefaria"))
    return rows


def resolve_alias_target(target: str, known_ref_titles: Sequence[str]) -> str | None:
    """Find the work an alias points at, tolerating a work that exists only as its parts.

    Several works are complex and expand into children, so no row carries the bare family name:
    Duties of the Heart becomes ten treatises, Shemirat HaLashon becomes two books. Someone
    searching "Chovot Halevavot" means the family, so the alias attaches to its first part.
    """
    if target in known_ref_titles:
        return target
    prefix = f"{target}, "
    for ref_title in known_ref_titles:
        if ref_title.startswith(prefix):
            return ref_title
    return None


def local_alias_rows(known_ref_titles: Iterable[str]) -> list[AliasRow]:
    """Turn the local file into rows, refusing an alias whose target does not exist.

    A typo in the YAML must fail the ingest rather than vanish silently.
    """
    known = list(known_ref_titles)
    rows: list[AliasRow] = []
    unknown: list[str] = []
    for alias, target in local_aliases():
        resolved = resolve_alias_target(target, known)
        if resolved is None:
            unknown.append(f"{alias!r} -> {target!r}")
            continue
        rows.append(AliasRow(ref_title=resolved, alias=alias, lang="en", source="local"))
    if unknown:
        raise ValueError(f"local aliases name works that are not in the catalog: {unknown}")
    return rows
