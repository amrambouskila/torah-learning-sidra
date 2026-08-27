"""Find a track ordinal from a reference Amram would recognise.

The inverse of ``position_at``. It exists for one job -- turning the positions in ``tracks.yaml``
into ordinals at seed time -- so it scans rather than indexes. Scanning Mishneh Torah's 15,143
halachos costs a second, once, against a lookup table that would have to be kept in step forever.

Two address shapes, because the catalog genuinely has two. Derived works answer to a ref string
(``Jeremiah 44``, ``Avodah Zarah 28b``). Parashat HaShavua's aliyot answer to a parsha name and an
aliyah number, which is how Amram writes his own position: "Ki Tavo, Shlishi".
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from sidra.calendar.calendar_day import ALIYOT_PER_PARSHA
from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.catalog.resolve import unit_at
from sidra.db.models import Track
from sidra.ledger.position import position_at, stored_granularity, stored_rows, works_for_track


async def resolve_position(session: AsyncSession, track: Track, given: str, *, current_ordinal: int) -> int:
    """Turn what Amram typed into a track ordinal.

    He writes the address, not the whole ref: ``5:7`` while learning Human Dispositions, ``38b``
    while learning Avoda Zara. The work supplying the rest is **the one he is standing in** -- a
    corpus track spans 84 works and ``5:7`` exists in most of them, so resolving against the first
    would silently record a position in a sefer he is nowhere near.

    A full ref still works, and so does a bare address in a later work, but only once the current
    one has been tried and failed.
    """
    text = given.strip()
    if not text:
        raise ValueError(f"{track.name_en}: no position given")

    works = await works_for_track(session, track)
    here: str | None = None
    if current_ordinal >= 1:
        here = (await position_at(session, track, current_ordinal)).work_ref_title

    candidates = [text]
    if here is not None:
        candidates.append(f"{here} {text}")
    candidates.extend(f"{work.ref_title} {text}" for work in works if work.ref_title != here)

    for candidate in candidates:
        try:
            return await ordinal_for_ref(session, track, candidate)
        except ValueError:
            continue
    raise ValueError(f"{track.name_en}: {given!r} is not a position in this track")


async def ordinal_for_ref(session: AsyncSession, track: Track, ref: str) -> int:
    """The 1-based track ordinal whose unit resolves to ``ref``.

    Raises naming the track and the ref rather than returning a sentinel: a position that does not
    resolve means the seed is wrong about where Amram is, which must stop the seed, not survive it.
    """
    granularity = stored_granularity(track.kind)
    consumed = 0
    for work in await works_for_track(session, track):
        if work.address_scheme is AddressScheme.STORED:
            rows = (await session.execute(stored_rows(work, granularity))).scalars().all()
            for offset, row in enumerate(rows, start=1):
                if row.resolved_ref == ref:
                    return consumed + offset
            consumed += len(rows)
            continue

        for seq in range(1, work.unit_count + 1):
            if unit_at(work.ref_title, work.address_scheme, work.shape, seq, labels=work.labels).ref == ref:
                return consumed + seq
        consumed += work.unit_count

    raise ValueError(f"{track.name_en}: {ref!r} is not among the track's {consumed} units")


async def ordinal_for_aliyah(session: AsyncSession, track: Track, parsha_en: str, aliyah: int) -> int:
    """The Chumash track's ordinal for a named parsha's nth aliyah.

    Parashat HaShavua interleaves 54 parsha rows with their 378 aliyot, so the answer is the
    aliyah's position among the aliyot alone -- counted off the rows rather than assumed from
    ``(parsha_index - 1) * 7 + aliyah``, which would be wrong the moment a parsha carried a maftir.
    """
    if not 1 <= aliyah <= ALIYOT_PER_PARSHA:
        raise ValueError(f"aliyah must be 1..{ALIYOT_PER_PARSHA}, got {aliyah}")

    ordinal = 0
    for work in await works_for_track(session, track):
        rows = (await session.execute(stored_rows(work, None))).scalars().all()
        current_parsha: str | None = None
        for row in rows:
            if row.granularity is Granularity.PARSHA:
                current_parsha = row.label_en
                continue
            ordinal += 1
            if current_parsha == parsha_en and row.ordinal == aliyah:
                return ordinal

    raise ValueError(f"{track.name_en}: no aliyah {aliyah} of {parsha_en!r} among the track's {ordinal} aliyot")
