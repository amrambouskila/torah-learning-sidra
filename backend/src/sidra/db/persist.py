from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.work_draft import WorkDraft
from sidra.db.models import Work


async def persist_works(
    session: AsyncSession,
    drafts: Sequence[WorkDraft],
    snapshot_id: uuid.UUID,
) -> list[Work]:
    """Write work drafts as rows. The only code in the project that writes ``Work``."""
    if not drafts:
        raise ValueError("no drafts supplied")

    works = [
        Work(
            corpus_id=draft.corpus_id,
            corpus_seq=draft.corpus_seq,
            index_title=draft.index_title,
            ref_title=draft.ref_title,
            title_he=draft.title_he,
            granularity=draft.granularity,
            address_scheme=draft.address_scheme,
            shape=list(draft.shape),
            labels=list(draft.labels) if draft.labels is not None else None,
            labels_he=list(draft.labels_he) if draft.labels_he is not None else None,
            unit_count=draft.unit_count,
            source=draft.source,
            snapshot_id=snapshot_id,
        )
        for draft in drafts
    ]
    session.add_all(works)
    await session.flush()
    return works
