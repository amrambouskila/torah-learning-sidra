"""Advancing by saying where you got to, rather than by counting units.

Amram knows he finished Human Dispositions 5:7. Working out that this was three halachos from
5:4, and that 5:7 is unit 289 of the corpus, is the app's job.
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration


async def _track_id(client: httpx.AsyncClient, name: str) -> str:
    rows = (await client.get("/api/tracks")).json()
    return next(row["id"] for row in rows if row["name_en"] == name)


async def test_a_bare_address_advances_within_the_current_work(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "47"})).json()
    assert body["track"]["at"]["ref"] == "Jeremiah 47"
    assert body["unit_count"] == 3
    assert body["was_replay"] is False


async def test_a_bare_address_resolves_against_the_work_he_is_standing_in(
    client: httpx.AsyncClient,
) -> None:
    """A corpus track spans many works and "47" exists in several. The one he is in wins, or the
    app silently records a position in a sefer he is nowhere near."""
    track_id = await _track_id(client, "Neviim")
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "45"})).json()
    assert body["track"]["at"]["ref"] == "Jeremiah 45"


async def test_a_whole_ref_works_too(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "Jeremiah 50"})).json()
    assert body["track"]["at"]["ref"] == "Jeremiah 50"
    assert body["unit_count"] == 6


async def test_a_daf_amud_address_works(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "David Hadar — Brachot")
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "14a"})).json()
    assert body["track"]["at"]["ref"] == "Berakhot 14a"
    assert body["unit_count"] == 2


async def test_the_count_is_derived_rather_than_asked_for(client: httpx.AsyncClient) -> None:
    """The whole point: he says where he got to and the app works out how far that was."""
    track_id = await _track_id(client, "Neviim")
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "44"})).json()
    assert body["was_replay"] is True
    assert body["unit_count"] == 0


async def test_a_reference_the_track_does_not_hold_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "nonsense"})
    assert response.status_code == 422
    assert "not a position in this track" in response.json()["detail"]


async def test_a_reference_past_the_end_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "999"})
    assert response.status_code == 422


async def test_an_empty_reference_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    assert (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "   "})).status_code == 422


async def test_giving_both_a_reference_and_an_ordinal_is_refused(client: httpx.AsyncClient) -> None:
    """Two answers to the same question can disagree."""
    track_id = await _track_id(client, "Neviim")
    response = await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "47", "to_ordinal": 123})
    assert response.status_code == 422


async def test_giving_neither_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    assert (await client.post(f"/api/tracks/{track_id}/advance", json={})).status_code == 422


async def test_an_ordinal_still_works_for_the_rail(client: httpx.AsyncClient) -> None:
    """A click on the rail already knows the ordinal it means; it should not have to name a ref."""
    track_id = await _track_id(client, "Neviim")
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": 123})).json()
    assert body["track"]["at"]["ref"] == "Jeremiah 47"


async def test_a_reference_carries_a_note_like_any_advance(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "David Hadar — Brachot")
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "14a", "note": "finished the sugya"})
    person = (await client.get("/api/chavrusas")).json()[0]
    assert person["sessions"][0]["note"] == "finished the sugya"


async def test_an_unopened_track_still_takes_a_reference(client: httpx.AsyncClient) -> None:
    """With no current position there is no work to borrow, so every work is tried in order."""
    track_id = await _track_id(client, "Likutei Sichot")
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "Likutei Sichot 2"})).json()
    assert body["track"]["actual_ordinal"] == 2


async def test_a_replay_reports_where_it_aimed(client: httpx.AsyncClient) -> None:
    """Without this the UI cannot say "Jeremiah 43 is 1 perek behind you" without another call."""
    track_id = await _track_id(client, "Neviim")
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "Jeremiah 43"})).json()
    assert body["was_replay"] is True
    assert body["advance_id"] is None
    assert body["to_ordinal"] == 120
    assert body["resolved_ordinal"] == 119


async def test_a_real_advance_reports_the_same_ordinal_it_recorded(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "Jeremiah 45"})).json()
    assert body["was_replay"] is False
    assert body["to_ordinal"] == 121
    assert body["resolved_ordinal"] == 121


async def test_a_malformed_date_is_refused_rather_than_crashing(client: httpx.AsyncClient) -> None:
    """It was parsed outside the try, so it surfaced as a 500."""
    track_id = await _track_id(client, "Neviim")
    response = await client.post(
        f"/api/tracks/{track_id}/advance", json={"to_ordinal": 121, "occurred_on": "not-a-date"}
    )
    assert response.status_code == 422
    assert "not-a-date" in response.json()["detail"]
