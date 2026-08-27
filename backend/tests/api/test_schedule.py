"""Correcting what a track is supposed to be up to.

What each operand does to days *before* today is the point of the whole feature, and it lives in
``test_schedule_history.py`` -- read through Stats, which has the pre-origin fallback that
``/api/tracks`` deliberately does not.
"""

from __future__ import annotations

import httpx
import pytest

from tests.api.conftest import on

pytestmark = pytest.mark.integration

JEREMIAH_44 = 120
JEREMIAH_46 = 122
JEREMIAH_47 = 123
JEREMIAH_50 = 126


async def _track_id(client: httpx.AsyncClient, name: str) -> str:
    rows = (await client.get("/api/tracks")).json()
    return next(row["id"] for row in rows if row["name_en"] == name)


async def _row(client: httpx.AsyncClient, name: str, params: dict[str, str] | None = None) -> dict[str, object]:
    rows = (await client.get("/api/tracks", params=params or {})).json()
    return next(row for row in rows if row["name_en"] == name)


async def _scheduled(client: httpx.AsyncClient, name: str, params: dict[str, str] | None = None) -> int:
    row = await _row(client, name, params)
    return int(row["scheduled_at"]["corpus_ordinal"])  # type: ignore[index]


# --- "it started on ___" ------------------------------------------------------------------------


async def test_moving_the_start_day_moves_the_schedule_by_one_period(client: httpx.AsyncClient) -> None:
    """Amram's case: the seeder billed its own run day, so the schedule ran a day ahead."""
    track_id = await _track_id(client, "Neviim")
    assert await _scheduled(client, "Neviim", on(3)) == JEREMIAH_50

    body = (await client.put(f"/api/tracks/{track_id}/schedule", params=on(3), json={"started_on": on(1)["on"]})).json()

    assert body["scheduled_at"]["corpus_ordinal"] == JEREMIAH_50 - 1
    assert await _scheduled(client, "Neviim", on(3)) == JEREMIAH_50 - 1


async def test_a_start_day_after_today_is_refused(client: httpx.AsyncClient) -> None:
    """periods_elapsed raises on an anchor ahead of the day being asked about."""
    track_id = await _track_id(client, "Neviim")
    response = await client.put(f"/api/tracks/{track_id}/schedule", json={"started_on": on(5)["on"]})
    assert response.status_code == 422
    assert "future" in response.json()["detail"]


async def test_a_track_that_has_not_begun_is_sent_to_the_start_date_endpoint(
    client: httpx.AsyncClient,
) -> None:
    track_id = await _track_id(client, "Likutei Sichot")
    response = await client.put(f"/api/tracks/{track_id}/schedule", json={"started_on": on(0)["on"]})
    assert response.status_code == 422
    assert "start date" in response.json()["detail"]


async def test_a_start_date_moves_with_the_anchor(client: httpx.AsyncClient) -> None:
    """``effective_anchor`` takes the later of the two, so leaving one behind would be a no-op."""
    track_id = await _track_id(client, "Likutei Sichot")
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": on(2)["on"]})

    body = (await client.put(f"/api/tracks/{track_id}/schedule", params=on(4), json={"started_on": on(3)["on"]})).json()

    assert body["starts_on"] == on(3)["on"]


# --- "it should be at ___ today" ----------------------------------------------------------------


async def test_naming_the_target_shifts_the_opening_position(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ordinal": JEREMIAH_46})).json()
    assert body["scheduled_at"]["corpus_ordinal"] == JEREMIAH_46
    assert body["debt"] == JEREMIAH_46 - JEREMIAH_44


async def test_a_typed_reference_names_the_target_too(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ref": "Jeremiah 46"})).json()
    assert body["scheduled_at"]["ref"] == "Jeremiah 46"


async def test_a_bare_address_resolves_against_the_work_he_is_standing_in(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ref": "46"})).json()
    assert body["scheduled_at"]["ref"] == "Jeremiah 46"


async def test_up_to_date_is_the_current_position_as_the_target(client: httpx.AsyncClient) -> None:
    """The UI's "I'm up to date" button is this request, not a second code path."""
    track_id = await _track_id(client, "Neviim")
    row = await _row(client, "Neviim")
    body = (await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ordinal": row["actual_ordinal"]})).json()
    assert body["debt"] == 0


async def test_a_target_past_the_end_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ordinal": 9999})
    assert response.status_code == 422
    assert "past the end" in response.json()["detail"]


async def test_an_unresolvable_reference_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ref": "Habakkuk 9"})
    assert response.status_code == 422


async def test_a_target_that_would_drive_the_anchor_below_one_is_refused(
    client: httpx.AsyncClient,
) -> None:
    """Three days in the schedule has moved three units, so asking for unit 1 puts the origin
    before the track begins."""
    track_id = await _track_id(client, "Neviim")
    response = await client.put(f"/api/tracks/{track_id}/schedule", params=on(3), json={"to_ordinal": 1})
    assert response.status_code == 422
    assert "before its first unit" in response.json()["detail"]


async def test_it_works_on_a_parsha_track(client: httpx.AsyncClient) -> None:
    """The calendar-driven schedule shares the anchor_ordinal + f(calendar) shape."""
    track_id = await _track_id(client, "Chumash")
    target = await _scheduled(client, "Chumash") - 1
    body = (await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ordinal": target})).json()
    assert body["scheduled_at"]["corpus_ordinal"] == target


async def test_a_day_outside_the_calendar_is_a_conflict(client: httpx.AsyncClient) -> None:
    """A parsha schedule accrues day by day, so a target it cannot bill against must say so."""
    track_id = await _track_id(client, "Chumash")
    response = await client.put(f"/api/tracks/{track_id}/schedule", params=on(400), json={"to_ordinal": 5})
    assert response.status_code == 409
    assert "calendar" in response.json()["detail"]


async def test_a_start_day_outside_the_calendar_is_a_conflict_too(client: httpx.AsyncClient) -> None:
    """The start-day route reaches the gap later than the target route does: its guards are pure
    date arithmetic, so the calendar is not consulted until the answering row is built."""
    track_id = await _track_id(client, "Chumash")
    response = await client.put(f"/api/tracks/{track_id}/schedule", params=on(400), json={"started_on": on(399)["on"]})
    assert response.status_code == 409
    assert "calendar" in response.json()["detail"]


# --- refusals shared by both routes --------------------------------------------------------------


async def test_a_chavrusa_track_has_no_schedule_to_correct(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "David Hadar — Brachot")
    response = await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ordinal": 5})
    assert response.status_code == 422
    assert "staleness" in response.json()["detail"]


async def test_exactly_one_of_the_three_is_required(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    assert (await client.put(f"/api/tracks/{track_id}/schedule", json={})).status_code == 422
    both = {"started_on": on(0)["on"], "to_ordinal": JEREMIAH_47}
    assert (await client.put(f"/api/tracks/{track_id}/schedule", json=both)).status_code == 422


async def test_an_unknown_track_is_a_404(client: httpx.AsyncClient) -> None:
    response = await client.put("/api/tracks/00000000-0000-0000-0000-000000000000/schedule", json={"to_ordinal": 1})
    assert response.status_code == 404
