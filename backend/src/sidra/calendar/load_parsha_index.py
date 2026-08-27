"""Build the parsha index out of the catalog."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.calendar.parsha_index import ParshaIndex
from sidra.catalog.granularity import Granularity
from sidra.db.models.learnable_unit import LearnableUnit

PARSHIYOS_IN_A_CYCLE = 54


async def load_parsha_index(session: AsyncSession) -> ParshaIndex:
    """Read the fifty-four parshiyos the catalog already stores.

    Refuses a short catalog rather than resolving against a partial list: a missing parsha would
    silently turn its week into a festival, and a week that bills nothing looks like ordinary
    calendar behaviour rather than like a broken crawl.
    """
    rows = (
        await session.execute(
            select(LearnableUnit.label_en, LearnableUnit.label_he)
            .where(LearnableUnit.granularity == Granularity.PARSHA)
            .order_by(LearnableUnit.seq)
        )
    ).all()
    if len(rows) != PARSHIYOS_IN_A_CYCLE:
        raise ValueError(
            f"the catalog holds {len(rows)} parshiyos, expected {PARSHIYOS_IN_A_CYCLE}; run 'sidra-db crawl'"
        )
    return ParshaIndex.from_names(rows)
