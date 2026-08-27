from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.db.models import Advance, Snapshot, TopicLink, Track, Work
from sidra.db.seed import DIRECT_CONFIDENCE, EIN_MISHPAT_KIND, INFERRED_CONFIDENCE, TUR_BRIDGE_KIND
from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.track_kind import TrackKind
from tests.api.conftest import AS_OF_DATE, HEBREW_AS_OF

pytestmark = pytest.mark.integration

HILCHOS = "Mishneh Torah, Human Dispositions"
DEOS_5_8 = 34


async def _snapshot_id(session: AsyncSession) -> uuid.UUID:
    return (await session.execute(select(Snapshot).limit(1))).scalar_one().id


async def _rambam_track(session: AsyncSession) -> Track:
    """A one-work Rambam track standing in Deos, which is where David Cohen actually is."""
    snapshot_id = await _snapshot_id(session)
    session.add(
        Work(
            corpus_id="mishneh_torah",
            corpus_seq=1,
            index_title=HILCHOS,
            ref_title=HILCHOS,
            title_he="הלכות דעות",
            granularity=Granularity.HALAKHAH,
            address_scheme=AddressScheme.NESTED,
            shape=[10] * 7,
            labels=None,
            labels_he=None,
            unit_count=70,
            source="sefaria",
            snapshot_id=snapshot_id,
        )
    )
    track = Track(
        name_en="David Cohen — Mishneh Torah",
        name_he="דוד כהן",
        category=Category.CHAVRUSA,
        kind=TrackKind.CURATED_QUEUE,
        corpus_id=None,
        work_ref_title=HILCHOS,
        rate=1,
        period=Period.NONE,
        anchor_date=AS_OF_DATE,
        anchor_ordinal=1,
        is_active=True,
    )
    session.add(track)
    await session.flush()
    session.add(
        Advance(
            track_id=track.id,
            from_ordinal=DEOS_5_8 - 1,
            to_ordinal=DEOS_5_8,
            unit_count=1,
            occurred_at=datetime.combine(AS_OF_DATE, datetime.min.time(), tzinfo=UTC),
            hebrew_date=HEBREW_AS_OF,
            note=None,
        )
    )
    await session.flush()
    return track


def _edge(
    snapshot_id: uuid.UUID,
    talmud_ref: str,
    *,
    inferred: bool = False,
    talmud_first: bool = False,
) -> TopicLink:
    halakhah = f"{HILCHOS} 5:8"
    from_ref, to_ref = (talmud_ref, halakhah) if talmud_first else (halakhah, talmud_ref)
    from_category, to_category = ("Talmud", "Halakhah") if talmud_first else ("Halakhah", "Talmud")
    return TopicLink(
        from_ref=from_ref,
        to_ref=to_ref,
        from_category=from_category,
        to_category=to_category,
        kind=TUR_BRIDGE_KIND if inferred else EIN_MISHPAT_KIND,
        anchor_group=from_ref,
        confidence=INFERRED_CONFIDENCE if inferred else DIRECT_CONFIDENCE,
        snapshot_id=snapshot_id,
    )


async def _seed_edges(session: AsyncSession, *edges: TopicLink) -> None:
    session.add_all(list(edges))
    await session.flush()


async def test_the_masechtos_are_ranked_as_a_distribution(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    """A share, not one recommendation: 71% Berakhot is unambiguous, 18% across a tail is not."""
    track = await _rambam_track(seeded_session)
    snapshot_id = await _snapshot_id(seeded_session)
    await _seed_edges(
        seeded_session,
        *[_edge(snapshot_id, f"Berakhot {n}a") for n in range(3, 6)],
        _edge(snapshot_id, "Shabbat 30a"),
    )

    rows = (await client.get(f"/api/alignment/{track.id}")).json()
    assert [row["masechta"] for row in rows] == ["Berakhot", "Shabbat"]
    assert [row["links"] for row in rows] == [3, 1]
    assert rows[0]["share"] == pytest.approx(0.75)
    assert sum(row["share"] for row in rows) == pytest.approx(1.0)


async def test_edges_count_in_both_directions(client: httpx.AsyncClient, seeded_session: AsyncSession) -> None:
    """The export records some edges Talmud to Halakhah and others the other way; both mean the same."""
    track = await _rambam_track(seeded_session)
    snapshot_id = await _snapshot_id(seeded_session)
    await _seed_edges(
        seeded_session,
        _edge(snapshot_id, "Berakhot 3a"),
        _edge(snapshot_id, "Berakhot 4a", talmud_first=True),
    )
    rows = (await client.get(f"/api/alignment/{track.id}")).json()
    assert rows[0]["links"] == 2


async def test_a_row_built_only_from_bridged_edges_is_marked_inferred(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    """A link bridged through Tur's siman numbering is an inference, never a citation."""
    track = await _rambam_track(seeded_session)
    snapshot_id = await _snapshot_id(seeded_session)
    await _seed_edges(
        seeded_session,
        _edge(snapshot_id, "Berakhot 3a"),
        _edge(snapshot_id, "Yoma 2a", inferred=True),
    )
    rows = {row["masechta"]: row["is_inferred"] for row in (await client.get(f"/api/alignment/{track.id}")).json()}
    assert rows == {"Berakhot": False, "Yoma": True}


async def test_a_masechta_with_real_citations_is_not_marked_inferred(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    track = await _rambam_track(seeded_session)
    snapshot_id = await _snapshot_id(seeded_session)
    await _seed_edges(
        seeded_session,
        _edge(snapshot_id, "Berakhot 3a"),
        _edge(snapshot_id, "Berakhot 4a", inferred=True),
    )
    rows = (await client.get(f"/api/alignment/{track.id}")).json()
    assert rows[0]["links"] == 2
    assert rows[0]["is_inferred"] is False


async def test_a_non_talmud_edge_is_ignored(client: httpx.AsyncClient, seeded_session: AsyncSession) -> None:
    """Ein Mishpat also points at Semag, Tur and the Shulchan Aruch; only Shas drives this queue."""
    track = await _rambam_track(seeded_session)
    link = _edge(await _snapshot_id(seeded_session), "Shulchan Arukh, Orach Chayim 2:6")
    link.to_category = "Halakhah"
    await _seed_edges(seeded_session, link)
    assert (await client.get(f"/api/alignment/{track.id}")).json() == []


async def test_a_track_with_no_edges_returns_nothing_rather_than_guessing(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    track = await _rambam_track(seeded_session)
    assert (await client.get(f"/api/alignment/{track.id}")).json() == []


async def test_an_unopened_track_has_no_alignment(client: httpx.AsyncClient) -> None:
    rows = (await client.get("/api/tracks")).json()
    track_id = next(row["id"] for row in rows if row["name_en"] == "Likutei Sichot")
    assert (await client.get(f"/api/alignment/{track_id}")).json() == []


async def test_the_ranking_is_capped(client: httpx.AsyncClient, seeded_session: AsyncSession) -> None:
    track = await _rambam_track(seeded_session)
    snapshot_id = await _snapshot_id(seeded_session)
    await _seed_edges(seeded_session, *[_edge(snapshot_id, f"Masechta{n} 2a") for n in range(30)])
    rows = (await client.get(f"/api/alignment/{track.id}", params={"limit": 5})).json()
    assert len(rows) == 5


async def test_an_unknown_track_is_a_404(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"/api/alignment/{uuid.uuid4()}")).status_code == 404


async def test_a_track_pointing_at_a_missing_work_is_a_conflict(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    """The catalog can be reseeded out from under the ledger; that must report, not crash."""
    track = Track(
        name_en="Orphaned",
        name_he="יתום",
        category=Category.CHAVRUSA,
        kind=TrackKind.CURATED_QUEUE,
        corpus_id=None,
        work_ref_title="Nonesuch",
        rate=1,
        period=Period.NONE,
        anchor_date=AS_OF_DATE,
        anchor_ordinal=1,
        is_active=True,
    )
    seeded_session.add(track)
    await seeded_session.flush()
    seeded_session.add(
        Advance(
            track_id=track.id,
            from_ordinal=0,
            to_ordinal=1,
            unit_count=1,
            occurred_at=datetime.combine(AS_OF_DATE, datetime.min.time(), tzinfo=UTC),
            hebrew_date=HEBREW_AS_OF,
            note=None,
        )
    )
    await seeded_session.flush()

    response = await client.get(f"/api/alignment/{track.id}")
    assert response.status_code == 409
    assert "Nonesuch" in response.json()["detail"]
