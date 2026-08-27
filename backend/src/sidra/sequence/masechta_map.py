"""Which masechta each work of a corpus draws on, computed once per catalog."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.alignment.aggregate import TALMUD_CATEGORY, masechta_of
from sidra.db.models import Snapshot, TopicLink, Work
from sidra.sequence.dominance import Dominance, dominant

_CACHE: dict[str, dict[str, Dominance | None]] = {}
"""Keyed by snapshot and corpus, so a re-seed invalidates it rather than serving the old map.

The map is a property of the catalog and the apparatus, never of the ledger -- it does not change
when Amram learns something -- so recomputing it per request would be waste rather than freshness.
"""


def shared_prefix(titles: Sequence[str]) -> str:
    """The longest opening every title shares, so one query can fetch the whole corpus's links."""
    if not titles:
        return ""
    shortest = min(titles, key=len)
    for size in range(len(shortest), 0, -1):
        head = shortest[:size]
        if all(title.startswith(head) for title in titles):
            return head
    return ""


async def masechta_map(session: AsyncSession, corpus_id: str) -> dict[str, Dominance | None]:
    """Ref title -> the masechta that work is about, for every work in the corpus."""
    snapshot = (await session.execute(select(Snapshot.id).order_by(Snapshot.created_at.desc()).limit(1))).scalar_one()
    key = f"{snapshot}:{corpus_id}"
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    works = (
        (await session.execute(select(Work).where(Work.corpus_id == corpus_id).order_by(Work.corpus_seq)))
        .scalars()
        .all()
    )
    counts: dict[str, dict[str, int]] = {work.ref_title: {} for work in works}
    longest_first = sorted(counts, key=len, reverse=True)
    prefix = shared_prefix([work.ref_title for work in works])

    links = (
        (
            await session.execute(
                select(TopicLink).where(TopicLink.from_ref.startswith(prefix) | TopicLink.to_ref.startswith(prefix))
            )
        )
        .scalars()
        .all()
    )
    for link in links:
        for ref, cited, cited_category in (
            (link.from_ref, link.to_ref, link.to_category),
            (link.to_ref, link.from_ref, link.from_category),
        ):
            if cited_category != TALMUD_CATEGORY:
                continue
            # Longest first, because "Mishneh Torah, Sabbath" is a prefix of nothing but itself
            # while a shorter title could otherwise swallow a longer one's refs.
            owner = next((title for title in longest_first if ref.startswith(f"{title} ")), None)
            if owner is None:
                continue
            name = masechta_of(cited)
            counts[owner][name] = counts[owner].get(name, 0) + 1
            break

    resolved = {title: dominant(found) for title, found in counts.items()}
    _CACHE[key] = resolved
    return resolved
