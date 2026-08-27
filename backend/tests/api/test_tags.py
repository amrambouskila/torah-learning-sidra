from __future__ import annotations

import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_the_seeded_tag_reports_how_many_tracks_wear_it(client: httpx.AsyncClient) -> None:
    tags = (await client.get("/api/tags")).json()
    assert [tag["name"] for tag in tags] == ["parsha"]
    assert tags[0]["name_he"] == "פרשה"
    assert tags[0]["track_count"] == 2


async def test_a_tag_can_be_created(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/tags", json={"name": "mussar", "name_he": "מוסר", "color": "#446644"})
    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["name_he"], body["track_count"]) == ("mussar", "מוסר", 0)
    assert [tag["name"] for tag in (await client.get("/api/tags")).json()] == ["mussar", "parsha"]


async def test_a_duplicate_name_is_refused(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/tags", json={"name": "parsha"})
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


async def test_an_empty_name_is_refused_by_the_schema(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/tags", json={"name": ""})).status_code == 422


async def test_a_tag_can_be_renamed_and_recoloured(client: httpx.AsyncClient) -> None:
    tag_id = (await client.get("/api/tags")).json()[0]["id"]
    body = (await client.patch(f"/api/tags/{tag_id}", json={"name": "parashah", "color": "#123456"})).json()
    assert (body["name"], body["color"]) == ("parashah", "#123456")
    assert body["track_count"] == 2


async def test_an_omitted_field_is_left_alone_rather_than_cleared(client: httpx.AsyncClient) -> None:
    tag_id = (await client.get("/api/tags")).json()[0]["id"]
    body = (await client.patch(f"/api/tags/{tag_id}", json={"color": "#123456"})).json()
    assert body["name_he"] == "פרשה"


async def test_a_field_can_be_cleared_deliberately(client: httpx.AsyncClient) -> None:
    tag_id = (await client.get("/api/tags")).json()[0]["id"]
    body = (await client.patch(f"/api/tags/{tag_id}", json={"name_he": None})).json()
    assert body["name_he"] is None


async def test_renaming_onto_an_existing_name_is_refused(client: httpx.AsyncClient) -> None:
    await client.post("/api/tags", json={"name": "mussar"})
    tag_id = next(tag["id"] for tag in (await client.get("/api/tags")).json() if tag["name"] == "parsha")
    response = await client.patch(f"/api/tags/{tag_id}", json={"name": "mussar"})
    assert response.status_code == 409


async def test_deleting_a_tag_removes_the_label_and_never_the_tracks(client: httpx.AsyncClient) -> None:
    tag_id = (await client.get("/api/tags")).json()[0]["id"]
    assert (await client.delete(f"/api/tags/{tag_id}")).status_code == 204
    assert (await client.get("/api/tags")).json() == []

    body = (await client.get("/api/today")).json()
    assert [row["name_en"] for row in body["daily"]] == ["Chumash", "Neviim"]
    assert all(row["tags"] == [] for row in body["daily"] + body["shabbat"])


async def test_an_unknown_tag_is_a_404(client: httpx.AsyncClient) -> None:
    missing = uuid.uuid4()
    assert (await client.patch(f"/api/tags/{missing}", json={"name": "x"})).status_code == 404
    assert (await client.delete(f"/api/tags/{missing}")).status_code == 404
