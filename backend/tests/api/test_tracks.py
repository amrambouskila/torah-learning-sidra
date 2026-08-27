from __future__ import annotations

import uuid

import httpx
import pytest

from tests.api.conftest import on

pytestmark = pytest.mark.integration


async def _track_id(client: httpx.AsyncClient, name: str) -> str:
    rows = (await client.get("/api/tracks")).json()
    return next(row["id"] for row in rows if row["name_en"] == name)


async def test_the_track_list_holds_every_active_track(client: httpx.AsyncClient) -> None:
    rows = (await client.get("/api/tracks")).json()
    assert [row["name_en"] for row in rows] == ["Chumash", "Neviim", "Likutei Sichot", "David Hadar — Brachot"]


async def test_a_detail_carries_a_rail_with_both_markers(client: httpx.AsyncClient) -> None:
    body = (await client.get(f"/api/tracks/{await _track_id(client, 'Neviim')}")).json()
    actual = [unit for unit in body["rail"] if unit["is_actual"]]
    scheduled = [unit for unit in body["rail"] if unit["is_scheduled"]]
    assert [unit["ref"] for unit in actual] == ["Jeremiah 44"]
    assert [unit["ref"] for unit in scheduled] == ["Jeremiah 47"]


async def test_every_rail_unit_names_its_sefer(client: httpx.AsyncClient) -> None:
    """The address alone is ambiguous. Neviim runs to Jeremiah 52 and starts over at Ezekiel 1;
    an aliyah is "Chamishi" in every parsha there is. The sefer is what tells them apart, and it
    comes off the catalog rather than being parsed back out of the ref."""
    neviim = await _track_id(client, "Neviim")
    rail = (await client.get(f"/api/tracks/{neviim}/rail", params={"from": 127, "to": 128})).json()
    assert [(unit["work_title_en"], unit["label_en"]) for unit in rail] == [
        ("Jeremiah", "51"),
        ("Jeremiah", "52"),
    ]
    # The fixture catalog stamps its Hebrew as "he-<title>"; the real Hebrew is asserted against
    # Sefaria in the live suite, where it arrives verbatim rather than being built here.
    assert rail[0]["work_title_he"] == "he-Jeremiah"

    chumash = await _track_id(client, "Chumash")
    aliyot = (await client.get(f"/api/tracks/{chumash}/rail", params={"from": 5, "to": 12})).json()
    assert [unit["label_en"] for unit in aliyot].count("Chamishi") == 2
    assert {unit["work_title_en"] for unit in aliyot} == {"Parashat HaShavua"}


async def test_the_rail_is_windowed_around_the_markers(client: httpx.AsyncClient) -> None:
    """The Shulchan Aruch track holds 1,705 simanim; serving every unit would be the heaviest
    response in the app for no gain."""
    body = (await client.get(f"/api/tracks/{await _track_id(client, 'Neviim')}", params={"radius": 3})).json()
    assert body["rail_from"] == 117
    assert body["rail_to"] == 126
    assert len(body["rail"]) == 10


async def test_the_rail_never_runs_past_either_end(client: httpx.AsyncClient) -> None:
    body = (await client.get(f"/api/tracks/{await _track_id(client, 'Likutei Sichot')}")).json()
    assert body["rail_from"] == 1
    assert body["rail"][0]["ordinal"] == 1


async def test_an_unknown_track_is_a_404(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/tracks/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_an_advance_moves_the_track_and_clears_the_debt(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": 123})).json()
    assert body["was_replay"] is False
    assert (body["from_ordinal"], body["to_ordinal"], body["unit_count"]) == (120, 123, 3)
    assert body["track"]["debt"] == 0
    assert body["track"]["at"]["ref"] == "Jeremiah 47"


async def test_an_advance_takes_a_note_that_reaches_the_session_log(client: httpx.AsyncClient) -> None:
    """One table is the history, the streak data and -- for a chavrusa track -- the session log."""
    track_id = await _track_id(client, "David Hadar — Brachot")
    await client.post(
        f"/api/tracks/{track_id}/advance",
        json={"to_ordinal": 26, "note": "Finished the sugya; picking up at the Mishnah."},
    )
    person = (await client.get("/api/chavrusas")).json()[0]
    # Berakhot 13a is the 23rd amud, so reaching 26 is three amudim in one sitting.
    assert person["sessions"][0]["note"] == "Finished the sugya; picking up at the Mishnah."
    assert (person["sessions"][0]["from_ordinal"], person["sessions"][0]["to_ordinal"]) == (23, 26)
    assert person["sessions"][0]["unit_count"] == 3


async def test_replaying_the_same_advance_does_not_double_count(client: httpx.AsyncClient) -> None:
    """The likeliest double post is a retried request, not a second session of learning."""
    track_id = await _track_id(client, "Neviim")
    first = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": 123})).json()
    second = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": 123})).json()
    assert first["was_replay"] is False
    assert second["was_replay"] is True
    assert second["unit_count"] == 0
    assert second["advance_id"] is None
    assert second["track"]["actual_ordinal"] == 123


async def test_an_advance_backwards_is_treated_as_a_replay(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": 123})
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": 121})).json()
    assert body["was_replay"] is True
    assert body["track"]["actual_ordinal"] == 123


async def test_an_advance_past_the_end_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": 9_999})
    assert response.status_code == 422
    assert "holds 128 units" in response.json()["detail"]


async def test_an_advance_below_one_is_refused_by_the_schema(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": 0})
    assert response.status_code == 422


async def test_an_advance_on_a_day_outside_the_calendar_is_a_conflict(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.post(
        f"/api/tracks/{track_id}/advance",
        json={"to_ordinal": 121, "occurred_on": "2030-01-01"},
    )
    assert response.status_code == 409


async def test_an_advance_can_be_dated(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (
        await client.post(
            f"/api/tracks/{track_id}/advance",
            json={"to_ordinal": 121, "occurred_on": on(4)["on"]},
        )
    ).json()
    assert body["track"]["last_advanced_on"] == on(4)["on"]


async def test_advancing_an_unknown_track_is_a_404(client: httpx.AsyncClient) -> None:
    response = await client.post(f"/api/tracks/{uuid.uuid4()}/advance", json={"to_ordinal": 1})
    assert response.status_code == 404


async def test_the_list_refuses_a_day_outside_the_calendar(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/tracks", params=on(400))
    assert response.status_code == 409


async def test_a_detail_refuses_a_day_outside_the_calendar(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/tracks/{await _track_id(client, 'Chumash')}", params=on(400))
    assert response.status_code == 409


# --- the rail span endpoint -----------------------------------------------------------------


async def test_a_span_returns_exactly_its_ordinals(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    rail = (await client.get(f"/api/tracks/{track_id}/rail", params={"from": 10, "to": 14})).json()
    assert [unit["ordinal"] for unit in rail] == [10, 11, 12, 13, 14]
    assert rail[0]["ref"] == "Joshua 10"


async def test_a_span_clamps_at_the_end_rather_than_erroring(client: httpx.AsyncClient) -> None:
    """A viewport that scrolls past the last unit is ordinary, not a mistake."""
    track_id = await _track_id(client, "Neviim")
    rail = (await client.get(f"/api/tracks/{track_id}/rail", params={"from": 126, "to": 200})).json()
    assert [unit["ordinal"] for unit in rail] == [126, 127, 128]


async def test_a_span_wholly_past_the_end_is_empty(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    assert (await client.get(f"/api/tracks/{track_id}/rail", params={"from": 500, "to": 520})).json() == []


async def test_both_markers_are_flagged_inside_a_span_that_holds_them(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    rail = (await client.get(f"/api/tracks/{track_id}/rail", params={"from": 118, "to": 125})).json()
    assert [unit["ordinal"] for unit in rail if unit["is_actual"]] == [120]
    assert [unit["ordinal"] for unit in rail if unit["is_scheduled"]] == [123]


async def test_a_span_holding_neither_marker_flags_nothing(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    rail = (await client.get(f"/api/tracks/{track_id}/rail", params={"from": 1, "to": 5})).json()
    assert not any(unit["is_actual"] or unit["is_scheduled"] for unit in rail)


async def test_an_inverted_span_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.get(f"/api/tracks/{track_id}/rail", params={"from": 20, "to": 10})
    assert response.status_code == 422
    assert "precedes from" in response.json()["detail"]


async def test_a_span_over_the_cap_is_refused(client: httpx.AsyncClient) -> None:
    """No single call carries a 15,143-halachah spine."""
    track_id = await _track_id(client, "Neviim")
    response = await client.get(f"/api/tracks/{track_id}/rail", params={"from": 1, "to": 501})
    assert response.status_code == 422
    assert "at most 500 units" in response.json()["detail"]


async def test_a_span_of_one_unit_works(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    rail = (await client.get(f"/api/tracks/{track_id}/rail", params={"from": 120, "to": 120})).json()
    assert len(rail) == 1
    assert rail[0]["is_actual"] is True


async def test_a_span_carries_sefaria_links_where_they_exist(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    rail = (await client.get(f"/api/tracks/{track_id}/rail", params={"from": 120, "to": 120})).json()
    assert rail[0]["sefaria_url"] == "https://www.sefaria.org/Jeremiah_44"

    local = await _track_id(client, "Likutei Sichot")
    rows = (await client.get(f"/api/tracks/{local}/rail", params={"from": 1, "to": 1})).json()
    assert rows[0]["sefaria_url"] is None


async def test_the_rail_of_an_unknown_track_is_a_404(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/tracks/{uuid.uuid4()}/rail", params={"from": 1, "to": 2})
    assert response.status_code == 404


async def test_the_rail_refuses_a_day_outside_the_calendar(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Chumash")
    response = await client.get(f"/api/tracks/{track_id}/rail", params={"from": 1, "to": 5, **on(400)})
    assert response.status_code == 409
