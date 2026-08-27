from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration


async def _track(client: httpx.AsyncClient, name: str) -> dict:
    rows = (await client.get("/api/tracks")).json()
    return next(row for row in rows if row["name_en"] == name)


async def test_a_parsha_track_declares_its_cycle_and_a_plain_one_does_not(client: httpx.AsyncClient) -> None:
    chumash = await _track(client, "Chumash")
    assert chumash["cycle_length"] == chumash["total"]
    assert chumash["reachable_to"] > chumash["total"]

    neviim = await _track(client, "Neviim")
    assert neviim["cycle_length"] is None
    assert neviim["reachable_to"] == neviim["total"]


async def test_a_cycle_track_is_never_finished_and_always_has_a_next_unit(client: httpx.AsyncClient) -> None:
    """The failure that arrives first. Reaching the last aliyah used to set is_finished, which
    disables Advance and empties up_next -- locking the track at exactly the moment the cycle
    turns and he should be starting Bereshit again."""
    chumash = await _track(client, "Chumash")
    total = chumash["total"]
    moved = await client.post(f"/api/tracks/{chumash['id']}/advance", json={"to_ordinal": total})
    assert moved.status_code == 200, moved.text

    row = await _track(client, "Chumash")
    assert row["actual_ordinal"] == total
    assert row["is_finished"] is False
    assert row["up_next"] is not None
    assert row["cycle_index"] == 1


async def test_the_turn_carries_the_position_round_and_the_ordinal_onward(client: httpx.AsyncClient) -> None:
    chumash = await _track(client, "Chumash")
    total = chumash["total"]
    first = (await client.get(f"/api/tracks/{chumash['id']}/rail", params={"from": 1, "to": 1})).json()[0]

    await client.post(f"/api/tracks/{chumash['id']}/advance", json={"to_ordinal": total})
    wrapped = await client.post(f"/api/tracks/{chumash['id']}/advance", json={"to_ordinal": total + 1})
    assert wrapped.status_code == 200, wrapped.text

    row = await _track(client, "Chumash")
    assert row["actual_ordinal"] == total + 1
    assert row["cycle_index"] == 2
    # The address is back at the first unit; the ordinal is not.
    assert row["at"]["ref"] == first["ref"]
    assert row["at"]["corpus_ordinal"] == total + 1


async def test_a_reference_typed_behind_him_stays_a_replay_across_the_turn(client: httpx.AsyncClient) -> None:
    """The refuted design lifted a backwards reference into the next cycle, turning "no, I stopped
    there" into a year of learning that never happened. With no undo, it must stay a no-op."""
    chumash = await _track(client, "Chumash")
    total = chumash["total"]
    await client.post(f"/api/tracks/{chumash['id']}/advance", json={"to_ordinal": total + 3})
    behind = (await client.get(f"/api/tracks/{chumash['id']}/rail", params={"from": 2, "to": 2})).json()[0]

    response = await client.post(f"/api/tracks/{chumash['id']}/advance", json={"to_ref": behind["ref"]})
    assert response.status_code == 200, response.text
    replayed = response.json()
    assert replayed["was_replay"] is True
    assert replayed["unit_count"] == 0
    assert (await _track(client, "Chumash"))["actual_ordinal"] == total + 3


async def test_a_reference_typed_ahead_resolves_inside_the_turn_he_is_in(client: httpx.AsyncClient) -> None:
    chumash = await _track(client, "Chumash")
    total = chumash["total"]
    await client.post(f"/api/tracks/{chumash['id']}/advance", json={"to_ordinal": total + 1})
    ahead = (await client.get(f"/api/tracks/{chumash['id']}/rail", params={"from": 3, "to": 3})).json()[0]

    response = await client.post(f"/api/tracks/{chumash['id']}/advance", json={"to_ref": ahead["ref"]})
    assert response.status_code == 200, response.text
    moved = response.json()
    assert moved["was_replay"] is False
    assert moved["to_ordinal"] == total + 3


async def test_an_advance_more_than_a_whole_turn_ahead_is_refused(client: httpx.AsyncClient) -> None:
    """The ceiling is what stands between a mistyped ordinal and a year of phantom learning."""
    chumash = await _track(client, "Chumash")
    refused = await client.post(
        f"/api/tracks/{chumash['id']}/advance", json={"to_ordinal": chumash["reachable_to"] + 1}
    )
    assert refused.status_code == 422
    assert "one whole cycle" in refused.json()["detail"]


async def test_the_rail_offers_exactly_what_the_endpoint_accepts(client: httpx.AsyncClient) -> None:
    """Three ceilings that disagree let the picker offer a unit the endpoint then refuses."""
    chumash = await _track(client, "Chumash")
    ceiling = chumash["reachable_to"]
    rail = (await client.get(f"/api/tracks/{chumash['id']}/rail", params={"from": 1, "to": ceiling + 5})).json()
    assert rail[-1]["ordinal"] == ceiling

    accepted = await client.post(f"/api/tracks/{chumash['id']}/advance", json={"to_ordinal": ceiling})
    assert accepted.status_code == 200, accepted.text


async def test_a_plain_track_still_stops_at_its_end(client: httpx.AsyncClient) -> None:
    neviim = await _track(client, "Neviim")
    refused = await client.post(f"/api/tracks/{neviim['id']}/advance", json={"to_ordinal": neviim["total"] + 1})
    assert refused.status_code == 422
    assert "past the end" in refused.json()["detail"]
