from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest

pytestmark = pytest.mark.integration


async def _stats(client: httpx.AsyncClient, **params: object) -> dict:
    response = await client.get("/api/stats", params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_it_answers_today_rather_than_409ing_on_tracks_that_have_not_begun(
    client: httpx.AsyncClient,
) -> None:
    """The recorded defect: several tracks have origins in the future, and asking them for a
    schedule made the whole screen a 409."""
    body = await _stats(client)
    assert body["window_days"] >= 1
    assert body["standing"]["not_started"] >= 0


async def test_the_window_is_clamped_to_the_ledger_and_says_so(client: httpx.AsyncClient) -> None:
    body = await _stats(client, window=365)
    assert body["requested_window_days"] == 365
    assert body["window_days"] < 365
    assert len(body["days"]) == body["window_days"]


async def test_the_standing_counts_every_track_exactly_once(client: httpx.AsyncClient) -> None:
    """Counted in tracks, never units: 21 amudim plus 4 perakim is not 25 of anything."""
    body = await _stats(client)
    rows = (await client.get("/api/tracks")).json()
    assert sum(body["standing"].values()) == len(rows)


async def test_a_tracks_net_is_billed_minus_learned_day_by_day(client: httpx.AsyncClient) -> None:
    body = await _stats(client)
    for row in body["tracks"]:
        assert len(row["net"]) == body["window_days"]
        if row["debt_now"] is not None:
            # The identity the whole grid rests on: today's debt is where it stood plus what
            # accrued across the window.
            assert row["debt_now"] == row["debt_then"] + sum(row["net"]), row["name_en"]


async def test_learning_closes_the_gap_and_idleness_opens_it(client: httpx.AsyncClient) -> None:
    """Three days on from the anchor, with nothing learned, the schedule has billed three days."""
    later = (date.fromisoformat((await _stats(client))["on"]) + timedelta(days=3)).isoformat()
    body = await _stats(client, on=later, window=10)
    idle = next(row for row in body["tracks"] if row["name_en"] == "Neviim")
    assert idle["learned_units"] == 0
    assert sum(idle["net"]) == 3

    tracks = (await client.get("/api/tracks")).json()
    neviim = next(row for row in tracks if row["name_en"] == "Neviim")
    moved = await client.post(f"/api/tracks/{neviim['id']}/advance", json={"to_ordinal": neviim["actual_ordinal"] + 5})
    assert moved.status_code == 200, moved.text

    after = await _stats(client, on=later, window=10)
    row = next(item for item in after["tracks"] if item["name_en"] == "Neviim")
    assert row["learned_units"] == 5
    assert row["days_learned"] == 1
    # The advance lands on the day it was recorded -- the window's first -- where five learned
    # against nothing billed closes the gap by five.
    assert row["net"][0] == -5
    assert sum(row["net"]) == 3 - 5


async def test_a_chavrusa_track_has_no_debt_and_bills_nothing(client: httpx.AsyncClient) -> None:
    body = await _stats(client)
    chavrusas = [row for row in body["tracks"] if row["debt_now"] is None]
    assert chavrusas
    for row in chavrusas:
        assert row["debt_then"] is None
        assert all(value <= 0 for value in row["net"])


async def test_the_seeders_opening_rows_are_not_counted_as_learning(client: httpx.AsyncClient) -> None:
    """A track sitting at its first unit has an advance row but has learned nothing."""
    body = await _stats(client)
    assert body["streak"]["current"] == 0
    assert all(row["opened_on"] is None for row in body["tracks"])


async def test_a_streak_appears_once_something_is_actually_learned(client: httpx.AsyncClient) -> None:
    tracks = (await client.get("/api/tracks")).json()
    neviim = next(row for row in tracks if row["name_en"] == "Neviim")
    await client.post(f"/api/tracks/{neviim['id']}/advance", json={"to_ordinal": neviim["actual_ordinal"] + 1})

    body = await _stats(client)
    assert body["streak"]["current"] == 1
    assert body["streak"]["longest"] == 1
    row = next(item for item in body["tracks"] if item["name_en"] == "Neviim")
    assert row["opened_on"] is not None


async def test_a_window_of_one_day_is_a_single_column(client: httpx.AsyncClient) -> None:
    body = await _stats(client, window=1)
    assert body["window_days"] == 1
    assert all(len(row["net"]) == 1 for row in body["tracks"])


async def test_an_out_of_range_window_is_refused_rather_than_clamped_silently(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.get("/api/stats", params={"window": 0})).status_code == 422
    assert (await client.get("/api/stats", params={"window": 5000})).status_code == 422


async def test_a_track_in_credit_counts_as_ahead(client: httpx.AsyncClient) -> None:
    """Negative debt is a good state, not an error: the surplus banks."""
    tracks = (await client.get("/api/tracks")).json()
    neviim = next(row for row in tracks if row["name_en"] == "Neviim")
    moved = await client.post(f"/api/tracks/{neviim['id']}/advance", json={"to_ordinal": neviim["actual_ordinal"] + 6})
    assert moved.status_code == 200, moved.text

    body = await _stats(client)
    assert body["standing"]["ahead"] == 1
    row = next(item for item in body["tracks"] if item["name_en"] == "Neviim")
    assert row["debt_now"] is not None
    assert row["debt_now"] < 0


async def test_a_day_the_calendar_does_not_reach_is_a_409_naming_the_gap(client: httpx.AsyncClient) -> None:
    """The Chumash's schedule needs a calendar day per day of history; a missing one must say so
    rather than under-accruing silently."""
    on = (date.fromisoformat((await _stats(client))["on"]) + timedelta(days=400)).isoformat()
    response = await client.get("/api/stats", params={"on": on})
    assert response.status_code == 409
    assert "calendar" in response.json()["detail"]
