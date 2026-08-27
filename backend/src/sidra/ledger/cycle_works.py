"""Which works repeat, read from ``data/cycles.yaml``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import cast

import yaml

CYCLES_PATH = Path(__file__).resolve().parents[3] / "data" / "cycles.yaml"


def parse_cycle_works(text: str) -> frozenset[str]:
    """The ref_titles of every work learned in a cycle. Refuses a repeated name."""
    payload = cast("dict[str, object]", yaml.safe_load(text))
    titles = [str(entry) for entry in cast("list[object]", payload["works"])]
    repeated = sorted({title for title in titles if titles.count(title) > 1})
    if repeated:
        raise ValueError(f"cycles.yaml names these works more than once: {', '.join(repeated)}")
    return frozenset(titles)


@lru_cache(maxsize=1)
def cycle_ref_titles(path: Path = CYCLES_PATH) -> frozenset[str]:
    return parse_cycle_works(path.read_text(encoding="utf-8"))
