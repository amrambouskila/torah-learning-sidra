from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.calendar.load_parsha_index import PARSHIYOS_IN_A_CYCLE, load_parsha_index
from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.db.models import LearnableUnit, Snapshot, Work

pytestmark = pytest.mark.integration

# The parshiyos these tests name; the rest of the cycle is filler, because what is under test is
# the reading and the count, not the list. Hebrew follows the catalog tests' placeholder form.
NAMED = ["Bereshit", "Lech Lecha", "Nitzavim", "Vayeilech"]


async def _seed_parshiyos(session: AsyncSession, *, count: int) -> None:
    snapshot = Snapshot(created_at=datetime.now(UTC), sefaria_version="test", unit_count=0, edge_count=0)
    session.add(snapshot)
    await session.flush()
    work = Work(
        corpus_id="torah",
        corpus_seq=1,
        index_title="Parashat HaShavua",
        ref_title="Parashat HaShavua",
        title_he="he-Parashat HaShavua",
        granularity=Granularity.PARSHA,
        address_scheme=AddressScheme.STORED,
        shape=[],
        labels=None,
        labels_he=None,
        unit_count=count,
        source="sefaria",
        snapshot_id=snapshot.id,
    )
    session.add(work)
    await session.flush()
    names = [*NAMED, *(f"Parsha {seq}" for seq in range(len(NAMED) + 1, count + 1))][:count]
    for seq, name in enumerate(names, start=1):
        session.add(
            LearnableUnit(
                work_id=work.id,
                seq=seq,
                ref_title="Parashat HaShavua",
                addr=[name],
                addr_types=["Parasha"],
                source="sefaria",
                snapshot_id=snapshot.id,
                granularity=Granularity.PARSHA,
                label_en=name,
                label_he=f"he-{name}",
            )
        )
    await session.flush()


async def test_the_index_comes_from_the_catalog_rather_than_a_written_list(db_session: AsyncSession) -> None:
    await _seed_parshiyos(db_session, count=PARSHIYOS_IN_A_CYCLE)
    index = await load_parsha_index(db_session)

    assert len(index.by_key) == PARSHIYOS_IN_A_CYCLE
    # The whole point: the Hebrew a resolved week carries is the catalog's, never the payload's.
    assert index.resolve("Lech-Lecha") == (("Lech Lecha",), ("he-Lech Lecha",))
    assert index.resolve("Nitzavim-Vayeilech") == (("Nitzavim", "Vayeilech"), ("he-Nitzavim", "he-Vayeilech"))


async def test_a_short_catalog_is_refused_rather_than_resolved_against(db_session: AsyncSession) -> None:
    """A missing parsha would turn its week into a festival, and a week billing nothing looks like
    ordinary calendar behaviour rather than a broken crawl."""
    await _seed_parshiyos(db_session, count=PARSHIYOS_IN_A_CYCLE - 1)
    with pytest.raises(ValueError, match="holds 53 parshiyos"):
        await load_parsha_index(db_session)
