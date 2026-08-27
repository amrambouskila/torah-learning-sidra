"""The catalog's expected shape, and the check that enforces it.

Every number here was measured against the live Sefaria API. They are the P1 gate: if one stops
holding, the ingester is wrong, not the number. Re-measure before editing any of them.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.db.models import LearnableUnit, TopicLink, Work

EXPECTED_COUNTS_PATH = Path(__file__).resolve().parents[2] / "data" / "expected_counts.json"


@lru_cache(maxsize=1)
def load_expected_counts() -> dict[str, Any]:
    return json.loads(EXPECTED_COUNTS_PATH.read_text(encoding="utf-8"))


async def _works_per_corpus(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(select(Work.corpus_id, func.count()).group_by(Work.corpus_id))
    return {corpus_id: count for corpus_id, count in rows.all()}


async def _units_per_corpus(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(select(Work.corpus_id, func.sum(Work.unit_count)).group_by(Work.corpus_id))
    return {corpus_id: int(total or 0) for corpus_id, total in rows.all()}


async def check_catalog(session: AsyncSession, expected: dict[str, Any]) -> list[str]:
    """Return one message per mismatch, empty when the catalog is exactly as expected."""
    failures: list[str] = []

    works = await _works_per_corpus(session)
    for corpus_id, count in expected["works"].items():
        if works.get(corpus_id) != count:
            failures.append(f"works[{corpus_id}]: expected {count}, found {works.get(corpus_id)}")

    units = await _units_per_corpus(session)
    for corpus_id, count in expected["units"].items():
        if units.get(corpus_id) != count:
            failures.append(f"units[{corpus_id}]: expected {count}, found {units.get(corpus_id)}")

    stored = await session.scalar(select(func.count()).select_from(LearnableUnit))
    if stored != expected["stored_units"]:
        failures.append(f"stored_units: expected {expected['stored_units']}, found {stored}")

    links = await session.scalar(select(func.count()).select_from(TopicLink))
    if links != expected["topic_links"]:
        failures.append(f"topic_links: expected {expected['topic_links']}, found {links}")

    total_units = sum(units.values())
    if total_units != expected["total_derivable_units"]:
        failures.append(f"total_derivable_units: expected {expected['total_derivable_units']}, found {total_units}")

    return failures
