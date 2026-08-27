from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.db.models import Advance, Chavrusa, Track
from tests.api.conftest import on

pytestmark = pytest.mark.integration


async def test_a_chavrusa_carries_their_tracks_and_sessions(client: httpx.AsyncClient) -> None:
    people = (await client.get("/api/chavrusas")).json()
    assert [person["name"] for person in people] == ["David Hadar"]
    assert [track["name_en"] for track in people[0]["tracks"]] == ["David Hadar — Brachot"]
    assert people[0]["sessions"][0]["from_ordinal"] == 22


async def test_staleness_is_measured_from_the_last_session(client: httpx.AsyncClient) -> None:
    person = (await client.get("/api/chavrusas", params=on(9))).json()[0]
    assert person["days_stale"] == 9
    assert person["tracks"][0]["debt"] is None


async def test_a_session_carries_its_hebrew_date(client: httpx.AsyncClient) -> None:
    session_row = (await client.get("/api/chavrusas")).json()[0]["sessions"][0]
    assert session_row["hebrew_date"]
    assert session_row["occurred_on"] == on(0)["on"]


async def test_someone_never_sat_with_sorts_above_any_measured_staleness(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    """A chavrusa with no sessions at all is the most urgent thing on the page."""
    seeded_session.add(Chavrusa(name="Zev — never met", notes="Introduced at a simcha."))
    await seeded_session.flush()

    people = (await client.get("/api/chavrusas", params=on(9))).json()
    assert [person["name"] for person in people] == ["Zev — never met", "David Hadar"]
    assert people[0]["days_stale"] is None
    assert people[0]["tracks"] == []
    assert people[0]["sessions"] == []


async def test_the_longest_stale_partner_comes_first(client: httpx.AsyncClient, seeded_session: AsyncSession) -> None:
    existing = (
        await seeded_session.execute(select(Track).where(Track.name_en == "David Hadar — Brachot"))
    ).scalar_one()
    seeded = (await seeded_session.execute(select(Advance).limit(1))).scalar_one()

    aharon = Chavrusa(name="Aharon")
    seeded_session.add(aharon)
    await seeded_session.flush()

    fresher = Track(
        name_en="Aharon — Brachot",
        name_he="אהרן",
        category=existing.category,
        kind=existing.kind,
        corpus_id=None,
        work_ref_title="Berakhot",
        rate=1,
        period=existing.period,
        anchor_date=existing.anchor_date,
        anchor_ordinal=1,
        chavrusa_id=aharon.id,
        is_active=True,
    )
    seeded_session.add(fresher)
    await seeded_session.flush()
    seeded_session.add(
        Advance(
            track_id=fresher.id,
            from_ordinal=0,
            to_ordinal=1,
            unit_count=1,
            occurred_at=seeded.occurred_at + timedelta(days=1),
            hebrew_date="x",
            note=None,
        )
    )
    await seeded_session.flush()

    people = (await client.get("/api/chavrusas", params=on(9))).json()
    assert [person["name"] for person in people] == ["David Hadar", "Aharon"]
    assert [person["days_stale"] for person in people] == [9, 8]


async def test_a_track_pointing_at_a_missing_work_is_a_conflict(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    """The catalog can be reseeded out from under the ledger; that must report, not crash."""
    existing = (
        await seeded_session.execute(select(Track).where(Track.name_en == "David Hadar — Brachot"))
    ).scalar_one()
    existing.work_ref_title = "Nonesuch"
    await seeded_session.flush()

    response = await client.get("/api/chavrusas")
    assert response.status_code == 409
    assert "Nonesuch" in response.json()["detail"]
