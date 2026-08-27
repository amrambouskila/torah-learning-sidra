from __future__ import annotations

import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration


async def _track(client: httpx.AsyncClient, name: str) -> dict:
    rows = (await client.get("/api/tracks")).json()
    return next(row for row in rows if row["name_en"] == name)


async def _make_tag(client: httpx.AsyncClient, name: str) -> dict:
    response = await client.post("/api/tags", json={"name": name, "name_he": None, "color": None})
    assert response.status_code == 201, response.text
    return response.json()


async def test_a_tag_can_be_put_on_a_track_and_taken_off_again(client: httpx.AsyncClient) -> None:
    """Nothing but the seeder wrote this link before, so a tag made on the Tags screen could be
    created, renamed and deleted but never actually worn by anything."""
    tag = await _make_tag(client, "oral torah")
    track = await _track(client, "Neviim")
    assert tag["name"] not in track["tags"]

    worn = await client.put(f"/api/tracks/{track['id']}/tags", json={"tag_ids": [tag["id"]]})
    assert worn.status_code == 200, worn.text
    assert worn.json()["tags"] == ["oral torah"]
    assert (await _track(client, "Neviim"))["tags"] == ["oral torah"]

    bare = await client.put(f"/api/tracks/{track['id']}/tags", json={"tag_ids": []})
    assert bare.status_code == 200, bare.text
    assert bare.json()["tags"] == []


async def test_the_set_replaces_rather_than_adds(client: httpx.AsyncClient) -> None:
    first, second = await _make_tag(client, "oral torah"), await _make_tag(client, "written torah")
    track = await _track(client, "Neviim")

    await client.put(f"/api/tracks/{track['id']}/tags", json={"tag_ids": [first["id"]]})
    swapped = await client.put(f"/api/tracks/{track['id']}/tags", json={"tag_ids": [second["id"]]})
    assert swapped.json()["tags"] == ["written torah"]


async def test_the_count_on_the_tags_screen_follows(client: httpx.AsyncClient) -> None:
    tag = await _make_tag(client, "oral torah")
    track = await _track(client, "Neviim")
    await client.put(f"/api/tracks/{track['id']}/tags", json={"tag_ids": [tag["id"]]})

    listed = next(row for row in (await client.get("/api/tags")).json() if row["id"] == tag["id"])
    assert listed["track_count"] == 1


async def test_deleting_the_tag_takes_the_label_and_leaves_the_track(client: httpx.AsyncClient) -> None:
    tag = await _make_tag(client, "oral torah")
    track = await _track(client, "Neviim")
    await client.put(f"/api/tracks/{track['id']}/tags", json={"tag_ids": [tag["id"]]})

    assert (await client.delete(f"/api/tags/{tag['id']}")).status_code == 204
    still_here = await _track(client, "Neviim")
    assert still_here["tags"] == []
    assert still_here["actual_ordinal"] == track["actual_ordinal"]


async def test_an_unknown_tag_is_a_404_and_changes_nothing(client: httpx.AsyncClient) -> None:
    tag = await _make_tag(client, "oral torah")
    track = await _track(client, "Neviim")
    await client.put(f"/api/tracks/{track['id']}/tags", json={"tag_ids": [tag["id"]]})

    missing = uuid.uuid4()
    refused = await client.put(f"/api/tracks/{track['id']}/tags", json={"tag_ids": [str(missing)]})
    assert refused.status_code == 404
    assert str(missing) in refused.json()["detail"]
    assert (await _track(client, "Neviim"))["tags"] == ["oral torah"]


async def test_the_same_tag_twice_is_refused(client: httpx.AsyncClient) -> None:
    tag = await _make_tag(client, "oral torah")
    track = await _track(client, "Neviim")
    response = await client.put(f"/api/tracks/{track['id']}/tags", json={"tag_ids": [tag["id"], tag["id"]]})
    assert response.status_code == 422


async def test_tagging_an_unknown_track_is_a_404(client: httpx.AsyncClient) -> None:
    response = await client.put(f"/api/tracks/{uuid.uuid4()}/tags", json={"tag_ids": []})
    assert response.status_code == 404


async def test_a_day_the_calendar_does_not_reach_is_a_409(client: httpx.AsyncClient) -> None:
    """The row comes back recomputed, so a day with no calendar cannot be rendered -- and saying
    so beats returning a row whose debt was quietly computed from nothing."""
    tag = await _make_tag(client, "oral torah")
    track = await _track(client, "Chumash")
    response = await client.put(
        f"/api/tracks/{track['id']}/tags",
        params={"on": "2030-01-01"},
        json={"tag_ids": [tag["id"]]},
    )
    assert response.status_code == 409
    assert "calendar" in response.json()["detail"]
