"""Setting, moving and clearing a track's start date."""

from __future__ import annotations

import uuid
from datetime import timedelta

import httpx
import pytest

from tests.api.conftest import on

pytestmark = pytest.mark.integration

TOMORROW = on(1)["on"]
NEXT_WEEK = on(7)["on"]


async def _track_id(client: httpx.AsyncClient, name: str) -> str:
    rows = (await client.get("/api/tracks")).json()
    return next(row["id"] for row in rows if row["name_en"] == name)


async def _row(client: httpx.AsyncClient, name: str) -> dict[str, object]:
    rows = (await client.get("/api/tracks")).json()
    return next(row for row in rows if row["name_en"] == name)


# --- setting one for the first time ---------------------------------------------------------


async def test_setting_a_start_date_stops_a_track_accruing(client: httpx.AsyncClient) -> None:
    """The case that prompted this: a sefer not opened yet should wait quietly, not run up a debt."""
    track_id = await _track_id(client, "Likutei Sichot")
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": None})
    assert (await _row(client, "Likutei Sichot"))["starts_in_days"] is None

    body = (await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK})).json()
    assert body["starts_on"] == NEXT_WEEK
    assert body["starts_in_days"] == 7
    assert body["debt"] == 0


async def test_the_track_owes_exactly_one_unit_on_the_day_it_starts(client: httpx.AsyncClient) -> None:
    """Not seven. This is the bug the feature surfaced."""
    track_id = await _track_id(client, "Likutei Sichot")
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": TOMORROW})
    body = (await client.get(f"/api/tracks/{track_id}", params=on(1))).json()
    assert body["track"]["debt"] == 1
    assert body["track"]["starts_in_days"] is None


async def test_starting_on_a_combined_week_owes_two(client: httpx.AsyncClient) -> None:
    """A combined week supplies two parshiyos, so beginning on one owes both."""
    track_id = await _track_id(client, "Likutei Sichot")
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK})
    body = (await client.get(f"/api/tracks/{track_id}", params=on(7))).json()
    assert body["track"]["debt"] == 2


async def test_a_start_date_can_be_moved(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Likutei Sichot")
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": TOMORROW})
    body = (await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK})).json()
    assert body["starts_on"] == NEXT_WEEK
    assert body["starts_in_days"] == 7


async def test_moving_a_start_date_keeps_banked_credit(client: httpx.AsyncClient) -> None:
    """Learning ahead during a countdown is banked; a later edit must not confiscate it."""
    track_id = await _track_id(client, "Likutei Sichot")
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK})
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": 3})

    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": TOMORROW})
    body = (await client.get(f"/api/tracks/{track_id}", params=on(1))).json()
    assert body["track"]["actual_ordinal"] == 3
    assert body["track"]["debt"] == -2
    assert body["track"]["days_ahead"] == 2


# --- clearing -------------------------------------------------------------------------------


async def test_clearing_a_future_start_date_starts_the_track_now(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Likutei Sichot")
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK})
    body = (await client.patch(f"/api/tracks/{track_id}", json={"starts_on": None})).json()
    assert body["starts_on"] is None
    assert body["starts_in_days"] is None
    assert body["debt"] == 1


async def test_clearing_leaves_the_track_readable(client: httpx.AsyncClient) -> None:
    """An anchor left parked in the future would 409 the whole Today screen on the next read."""
    track_id = await _track_id(client, "Likutei Sichot")
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK})
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": None})
    assert (await client.get("/api/today")).status_code == 200


async def test_clearing_a_track_that_never_had_one_is_harmless(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    before = await _row(client, "Neviim")
    body = (await client.patch(f"/api/tracks/{track_id}", json={"starts_on": None})).json()
    assert body["debt"] == before["debt"]


# --- what it refuses -------------------------------------------------------------------------


async def test_a_track_with_a_real_backlog_is_refused(client: httpx.AsyncClient) -> None:
    """Rebasing clears what a track owes. On a track being learned that erases real history."""
    track_id = await _track_id(client, "Neviim")
    response = await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "owes 3 perakim" in detail
    assert "clears that" in detail


async def test_a_backlog_can_be_cleared_when_it_is_asked_for(client: httpx.AsyncClient) -> None:
    """Refused by accident, never forbidden: it is his ledger and his decision."""
    track_id = await _track_id(client, "Neviim")
    body = (await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK, "forgive": True})).json()
    assert body["starts_on"] == NEXT_WEEK
    assert body["debt"] == 0


async def test_a_track_seeded_at_its_first_unit_owes_nothing_and_needs_no_permission(
    client: httpx.AsyncClient,
) -> None:
    """Likutey Moharan's shape: the old note recorded 1:1 as a position, not as learning done.
    It has an actual_ordinal but no debt, so a start date erases nothing."""
    track_id = await _track_id(client, "Chumash")
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": 8})
    row = await _row(client, "Chumash")
    assert row["actual_ordinal"] > 0
    assert row["debt"] == 0

    response = await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK})
    assert response.status_code == 200


async def test_the_measured_debt_survives_a_refused_attempt(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK})
    assert (await _row(client, "Neviim"))["debt"] == 3


async def test_a_chavrusa_track_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "David Hadar — Brachot")
    response = await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK})
    assert response.status_code == 422
    assert "staleness" in response.json()["detail"]


async def test_a_date_in_the_past_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Likutei Sichot")
    response = await client.patch(f"/api/tracks/{track_id}", json={"starts_on": on(-1)["on"]})
    assert response.status_code == 422
    assert "in the past" in response.json()["detail"]


async def test_today_is_accepted(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Likutei Sichot")
    body = (await client.patch(f"/api/tracks/{track_id}", json={"starts_on": on(0)["on"]})).json()
    assert body["starts_on"] == on(0)["on"]
    assert body["debt"] == 1


async def test_a_date_years_out_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Likutei Sichot")
    response = await client.patch(f"/api/tracks/{track_id}", json={"starts_on": on(365 * 3)["on"]})
    assert response.status_code == 422
    assert "years out" in response.json()["detail"]


async def test_a_mistyped_key_is_refused_rather_than_ignored(client: httpx.AsyncClient) -> None:
    """With one field, a silent no-op answering 200 would be the worst possible outcome."""
    track_id = await _track_id(client, "Likutei Sichot")
    response = await client.patch(f"/api/tracks/{track_id}", json={"starts_at": NEXT_WEEK})
    assert response.status_code == 422


async def test_an_unknown_track_is_a_404(client: httpx.AsyncClient) -> None:
    response = await client.patch(f"/api/tracks/{uuid.uuid4()}", json={"starts_on": NEXT_WEEK})
    assert response.status_code == 404


async def test_a_track_advanced_during_its_countdown_can_still_be_edited(client: httpx.AsyncClient) -> None:
    """Nothing has accrued during a countdown, so a rebase forgives nothing whatever actual says."""
    track_id = await _track_id(client, "Likutei Sichot")
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK})
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": 2})
    response = await client.patch(f"/api/tracks/{track_id}", json={"starts_on": TOMORROW})
    assert response.status_code == 200


async def test_an_unopened_track_whose_start_has_passed_can_be_pushed_back(
    client: httpx.AsyncClient,
) -> None:
    """He set it for last week, never opened it, and wants to try again."""
    track_id = await _track_id(client, "Likutei Sichot")
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": on(0)["on"]})
    response = await client.patch(f"/api/tracks/{track_id}", params=on(3), json={"starts_on": on(9)["on"]})
    assert response.status_code == 200
    assert response.json()["starts_in_days"] == 6


# --- the roadmap follows ---------------------------------------------------------------------


async def test_a_not_yet_started_track_projects_from_its_start_date(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Likutei Sichot")
    await client.patch(f"/api/tracks/{track_id}", json={"starts_on": NEXT_WEEK})
    row = next(r for r in (await client.get("/api/roadmap")).json() if r["track_id"] == track_id)
    assert row["projected_finish"] is not None
    assert row["projected_finish"] > NEXT_WEEK


async def test_an_omitted_body_field_clears_rather_than_surprising(client: httpx.AsyncClient) -> None:
    """One field means one operation: an empty body is an explicit clear, not a no-op."""
    track_id = await _track_id(client, "Likutei Sichot")
    body = (await client.patch(f"/api/tracks/{track_id}", json={})).json()
    assert body["starts_on"] is None


def test_the_fixture_dates_are_what_the_tests_assume() -> None:
    from tests.api.conftest import AS_OF_DATE

    assert TOMORROW == (AS_OF_DATE + timedelta(days=1)).isoformat()


async def test_a_day_outside_the_calendar_is_a_conflict(client: httpx.AsyncClient) -> None:
    """Starting a parsha track beyond the snapshot needs calendar days nobody has stored."""
    track_id = await _track_id(client, "Likutei Sichot")
    far = on(400)
    response = await client.patch(f"/api/tracks/{track_id}", params=far, json={"starts_on": far["on"]})
    assert response.status_code == 409
    assert "sidra-db calendar" in response.json()["detail"]


async def test_a_track_being_learned_cannot_be_checked_beyond_the_calendar(
    client: httpx.AsyncClient,
) -> None:
    """Working out whether a backlog would be cleared needs the schedule, and the schedule needs
    the calendar. Better to say so than to guess at the number."""
    track_id = await _track_id(client, "Chumash")
    far = on(400)
    response = await client.patch(f"/api/tracks/{track_id}", params=far, json={"starts_on": far["on"]})
    assert response.status_code == 409
    assert "sidra-db calendar" in response.json()["detail"]
