"""Turn a track ordinal into a real reference.

A ``CORPUS`` track streams across every work in its corpus in ``corpus_seq`` order, which is what
makes Neviim one 380-perek run rather than twenty-one separate ones: after Yirmiyahu 52 comes
Yechezkel 1, and Amram never chooses it. The other kinds name one work at a time.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.catalog.resolve import unit_at
from sidra.db.models import LearnableUnit, Track, Work
from sidra.ledger.track_kind import TrackKind

SEFARIA_SOURCE = "sefaria"


@dataclass(frozen=True, slots=True)
class Position:
    """Where a track stands, resolved through the catalog."""

    work_ref_title: str
    work_title_he: str
    seq_in_work: int
    ref: str
    label_en: str
    label_he: str
    corpus_ordinal: int

    granularity: Granularity
    """What the unit *is*, which is what lets a badge say "amudim" rather than "units"."""

    is_linkable: bool
    """Whether the ref is a real Sefaria ref. Likutei Sichot and The Midrash Says are not on
    Sefaria at all, so the UI shows their position without a deep link -- a normal state."""


def stored_granularity(kind: TrackKind) -> Granularity | None:
    """Which granularity a track kind runs on inside a STORED work, if it runs on only one.

    Parashat HaShavua holds 432 rows -- 54 parshiyos interleaved with their 378 aliyot -- so an
    aliyah-a-day track that indexed the rows directly would land on a parsha every eighth day.
    """
    return Granularity.ALIYAH if kind is TrackKind.PARSHA_ALIYAH else None


def stored_rows(work: Work, granularity: Granularity | None) -> Select[tuple[LearnableUnit]]:
    """A STORED work's rows in order, narrowed to one granularity when the track runs on one."""
    query = select(LearnableUnit).where(LearnableUnit.work_id == work.id)
    if granularity is not None:
        query = query.where(LearnableUnit.granularity == granularity)
    return query.order_by(LearnableUnit.seq)


def _like_escape(value: str) -> str:
    """Escape LIKE wildcards so a title is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def works_for_track(session: AsyncSession, track: Track) -> list[Work]:
    """The works a track runs through, in order.

    A ``CORPUS`` track takes its whole corpus. Every other kind names one work -- but several of
    the sefarim in this sidra exist in the catalog only as their parts, because Sefaria splits a
    complex work into them: there is no ``Tanya``, only ``Tanya, Part I; Likkutei Amarim`` and its
    four siblings. Naming the parent therefore takes the parent if it exists and otherwise its
    parts in order, which is what makes Tanya one 118-perek track rather than five.
    """
    if track.kind is TrackKind.CORPUS:
        if track.corpus_id is None:
            raise ValueError(f"{track.name_en}: a corpus track must name a corpus")
        rows = await session.execute(select(Work).where(Work.corpus_id == track.corpus_id).order_by(Work.corpus_seq))
        return list(rows.scalars().all())

    if track.work_ref_title is None:
        raise ValueError(f"{track.name_en}: a {track.kind.value} track must name a work")
    title = track.work_ref_title
    rows = await session.execute(
        select(Work)
        .where(or_(Work.ref_title == title, Work.ref_title.like(f"{_like_escape(title)}, %", escape="\\")))
        .order_by(Work.corpus_seq)
    )
    works = list(rows.scalars().all())
    if not works:
        raise ValueError(f"{track.name_en}: no work titled {title!r} is in the catalog")
    return works


async def _work_total(session: AsyncSession, work: Work, granularity: Granularity | None) -> int:
    """How many units of the track's own granularity this work holds."""
    if work.address_scheme is not AddressScheme.STORED:
        return work.unit_count
    subquery = stored_rows(work, granularity).order_by(None).subquery()
    return int(await session.scalar(select(func.count()).select_from(subquery)) or 0)


async def track_total(session: AsyncSession, track: Track) -> int:
    """How many units the track holds in total."""
    granularity = stored_granularity(track.kind)
    total = 0
    for work in await works_for_track(session, track):
        total += await _work_total(session, work, granularity)
    return total


async def _stored_position(
    session: AsyncSession,
    work: Work,
    seq: int,
    corpus_ordinal: int,
    granularity: Granularity | None,
) -> Position:
    """A STORED work keeps its units as rows, because they carry data no count can produce.

    Indexed by offset rather than by ``seq``: once a granularity filter is on, the surviving rows
    are no longer numbered 1..N. The caller has already bounded ``seq`` by the same filtered count,
    so a miss here is a broken invariant and ``scalar_one`` is right to raise.
    """
    row = (await session.execute(stored_rows(work, granularity).offset(seq - 1).limit(1))).scalar_one()
    return Position(
        work_ref_title=work.ref_title,
        work_title_he=work.title_he,
        seq_in_work=seq,
        ref=row.resolved_ref or work.ref_title,
        label_en=row.label_en,
        label_he=row.label_he,
        corpus_ordinal=corpus_ordinal,
        granularity=row.granularity,
        is_linkable=work.source == SEFARIA_SOURCE,
    )


async def position_at(session: AsyncSession, track: Track, corpus_ordinal: int) -> Position:
    """Resolve a 1-based track ordinal into a catalog reference.

    The ordinal runs across the whole corpus, so this walks the works to find the one holding it
    and then delegates to ``unit_at`` -- or to the stored rows, for a ``STORED`` work.
    """
    if corpus_ordinal < 1:
        raise ValueError(f"ordinal must be at least 1, got {corpus_ordinal}")

    granularity = stored_granularity(track.kind)
    consumed = 0
    for work in await works_for_track(session, track):
        held = await _work_total(session, work, granularity)
        if corpus_ordinal <= consumed + held:
            seq = corpus_ordinal - consumed
            if work.address_scheme is AddressScheme.STORED:
                return await _stored_position(session, work, seq, corpus_ordinal, granularity)
            unit = unit_at(
                work.ref_title,
                work.address_scheme,
                work.shape,
                seq,
                labels=work.labels,
                labels_he=work.labels_he,
            )
            return Position(
                work_ref_title=work.ref_title,
                work_title_he=work.title_he,
                seq_in_work=seq,
                ref=unit.ref,
                label_en=unit.label_en,
                label_he=unit.label_he,
                corpus_ordinal=corpus_ordinal,
                granularity=work.granularity,
                is_linkable=work.source == SEFARIA_SOURCE,
            )
        consumed += held

    raise ValueError(f"{track.name_en}: ordinal {corpus_ordinal} is past the end; the track holds {consumed} units")
