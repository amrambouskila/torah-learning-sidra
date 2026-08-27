"""Verify the parsha and aliyah ingest against the real Sefaria API.

Run deliberately:  uv run pytest -m live
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from sidra.catalog.granularity import Granularity
from sidra.catalog.ingest_parsha import ingest_parshiyos
from sidra.catalog.sefaria_client import SefariaClient
from sidra.catalog.stored_unit import StoredUnitRow
from sidra.catalog.work_draft import WorkDraft
from sidra.constants import SEFARIA_BASE_URL

pytestmark = pytest.mark.live


@pytest.fixture(scope="session")
async def parsha() -> AsyncIterator[tuple[WorkDraft, list[StoredUnitRow]]]:
    async with httpx.AsyncClient(timeout=120.0) as http:
        yield await ingest_parshiyos(SefariaClient(http, SEFARIA_BASE_URL))


def test_the_five_chumashim_yield_fifty_four_parshiyos(
    parsha: tuple[WorkDraft, list[StoredUnitRow]],
) -> None:
    _, rows = parsha
    assert sum(1 for row in rows if row.granularity is Granularity.PARSHA) == 54


def test_they_yield_three_hundred_seventy_eight_aliyot(
    parsha: tuple[WorkDraft, list[StoredUnitRow]],
) -> None:
    _, rows = parsha
    assert sum(1 for row in rows if row.granularity is Granularity.ALIYAH) == 378
    assert len(rows) == 432


def test_every_parsha_has_exactly_seven_children(parsha: tuple[WorkDraft, list[StoredUnitRow]]) -> None:
    _, rows = parsha
    children: dict[int, int] = {}
    for row in rows:
        if row.parent_seq is not None:
            children[row.parent_seq] = children.get(row.parent_seq, 0) + 1
    assert set(children.values()) == {7}
    assert len(children) == 54


def test_ki_tavo_shlishi_is_sefarias_own_range(parsha: tuple[WorkDraft, list[StoredUnitRow]]) -> None:
    """The real Chumash position, resolved from Sefaria's string rather than built."""
    _, rows = parsha
    ki_tavo_seq = next(r.seq for r in rows if r.label_en == "Ki Tavo")
    shlishi = next(r for r in rows if r.parent_seq == ki_tavo_seq and r.ordinal == 3)
    assert shlishi.label_en == "Shlishi"
    assert shlishi.label_he == "שלישי"
    assert shlishi.resolved_ref == "Deuteronomy 26:16-26:19"


def test_every_row_carries_hebrew(parsha: tuple[WorkDraft, list[StoredUnitRow]]) -> None:
    _, rows = parsha
    for row in rows:
        assert row.label_he, row.label_en
        assert any("֐" <= character <= "׿" for character in row.label_he), row.label_en


async def test_orchot_tzadikim_has_twenty_eight_named_gates() -> None:
    """Shape reports 29 with the 29th empty; the alt-struct names all 28."""
    from sidra.catalog.granularity import Granularity
    from sidra.catalog.ingest_named import NamedWorkSpec, ingest_named_work
    from sidra.catalog.resolve import unit_at

    async with httpx.AsyncClient(timeout=90.0) as http:
        client = SefariaClient(http, SEFARIA_BASE_URL)
        draft = await ingest_named_work(
            client,
            NamedWorkSpec(
                corpus_id="mussar",
                corpus_seq=1,
                ref_title="Orchot Tzadikim",
                alt_key="Gate",
                granularity=Granularity.GATE,
            ),
        )

    assert draft.unit_count == 28
    assert draft.labels is not None and len(draft.labels) == 28
    assert draft.labels_he is not None and len(draft.labels_he) == 28
    assert not any(label.endswith("\n") for label in draft.labels_he)

    # Shaar HaCharata is gate 11 -- the real Shabbat position.
    gate_11 = unit_at(
        draft.ref_title,
        draft.address_scheme,
        draft.shape,
        11,
        labels=draft.labels,
        labels_he=draft.labels_he,
    )
    assert "REMORSE" in gate_11.label_en
    assert "החרטה" in gate_11.label_he
    assert gate_11.ref == "Orchot Tzadikim 11"
