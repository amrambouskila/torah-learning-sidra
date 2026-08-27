"""How big each body of learning is, counted off the catalog.

Deliberately not the ledger. The Pace Explorer answers "what would a cycle cost", not "how am I
doing" -- so nothing here reads a track, a position or a debt, and the same numbers hold whether
Amram is twenty amudim behind or has never opened the sefer.

The counting is a fold over every work in one query rather than SQL per row: a work's ``shape`` is
a JSON array whose levels mean different things per address scheme, and unpicking that in SQL buys
nothing and costs the ability to test it without a database.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.bavli_amudim import real_amudim
from sidra.catalog.granularity import Granularity
from sidra.db.models import LearnableUnit, Work
from sidra.ledger.unit_noun import unit_nouns
from sidra.pace.pace_scope import PaceScope


@dataclass(frozen=True, slots=True)
class CountedWork:
    """The slice of a ``Work`` the counting needs, so the fold is testable without a database."""

    corpus_id: str
    ref_title: str
    granularity: Granularity
    shape: Sequence[int]
    unit_count: int


@dataclass(frozen=True, slots=True)
class ScopeCount:
    """One scope and how many units it holds."""

    scope: PaceScope
    total: int


def _selected(works: Sequence[CountedWork], scope: PaceScope) -> list[CountedWork]:
    chosen = [
        work
        for work in works
        if (not scope.corpus_ids or work.corpus_id in scope.corpus_ids)
        and (scope.ref_title_prefix is None or work.ref_title.startswith(scope.ref_title_prefix))
        and not any(work.ref_title.endswith(title) for title in scope.exclude_titles)
    ]
    # Tanach is three corpora, one of which also carries the parsha cycle's stored rows.
    if scope.granularity == Granularity.PEREK.value and len(scope.corpus_ids) > 1:
        chosen = [work for work in chosen if work.granularity is Granularity.PEREK]
    return chosen


def _dapim(work: CountedWork) -> int:
    """Amudim folded to daf. 2a and 2b are one daf; a masechta with neither has none."""
    return len({label[:-1] for label in real_amudim(work.shape)})


def count_scope(works: Sequence[CountedWork], scope: PaceScope, aliyot: int) -> int:
    """How many units this scope holds, by whichever rule it declares."""
    if scope.rule == "aliyot":
        return aliyot
    chosen = _selected(works, scope)
    if scope.rule == "total":
        return sum(work.unit_count for work in chosen)
    if scope.rule == "parents":
        return sum(len(work.shape) for work in chosen)
    if scope.rule == "children":
        return sum(sum(work.shape) for work in chosen)
    return sum(_dapim(work) for work in chosen)


def nouns_for(scope: PaceScope) -> tuple[str, str]:
    """The scope's own nouns when it declares them, otherwise the domain's."""
    if scope.unit_singular is not None and scope.unit_plural is not None:
        return scope.unit_singular, scope.unit_plural
    return unit_nouns(Granularity(scope.granularity))


async def read_catalog(session: AsyncSession) -> tuple[list[CountedWork], int]:
    """Every work plus the aliyah count, in two queries for the whole screen."""
    rows = (
        await session.execute(select(Work.corpus_id, Work.ref_title, Work.granularity, Work.shape, Work.unit_count))
    ).all()
    works = [
        CountedWork(
            corpus_id=corpus_id,
            ref_title=ref_title,
            granularity=granularity,
            shape=list(shape),
            unit_count=unit_count,
        )
        for corpus_id, ref_title, granularity, shape, unit_count in rows
    ]
    aliyot = int(
        await session.scalar(
            select(func.count()).select_from(LearnableUnit).where(LearnableUnit.granularity == Granularity.ALIYAH)
        )
        or 0
    )
    return works, aliyot


async def count_all(session: AsyncSession, scopes: Sequence[PaceScope]) -> list[ScopeCount]:
    """Count every scope. A scope that comes out empty is dropped: a zero row is a wrong answer."""
    works, aliyot = await read_catalog(session)
    counted = [ScopeCount(scope=scope, total=count_scope(works, scope, aliyot)) for scope in scopes]
    return [row for row in counted if row.total > 0]
