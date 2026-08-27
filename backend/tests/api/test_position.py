"""Correcting where a track actually stands."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from sidra.api.deps import safety_copy_path
from sidra.ledger.ledger_file import read_ledger
from tests.api.conftest import on

pytestmark = pytest.mark.integration

JEREMIAH_44 = 120
JEREMIAH_48 = 124
JEREMIAH_49 = 125


async def _track_id(client: httpx.AsyncClient, name: str) -> str:
    rows = (await client.get("/api/tracks")).json()
    return next(row["id"] for row in rows if row["name_en"] == name)


async def _row(client: httpx.AsyncClient, track_id: str) -> dict[str, object]:
    rows = (await client.get("/api/tracks")).json()
    return next(row for row in rows if row["id"] == track_id)


async def _at(client: httpx.AsyncClient, track_id: str) -> int:
    return int((await _row(client, track_id))["actual_ordinal"])  # type: ignore[arg-type]


async def test_a_confirmed_correction_moves_the_position_back(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": JEREMIAH_49})

    body = (
        await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_48, "confirm": True})
    ).json()

    assert body["from_ordinal"] == JEREMIAH_49
    assert body["to_ordinal"] == JEREMIAH_48
    assert body["removed_units"] == 1
    assert body["moved"] is True
    assert body["track"]["actual_ordinal"] == JEREMIAH_48
    assert await _at(client, track_id) == JEREMIAH_48


async def test_it_refuses_without_confirmation_and_says_what_it_would_remove(
    client: httpx.AsyncClient,
) -> None:
    track_id = await _track_id(client, "Neviim")
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": JEREMIAH_49})

    response = await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_48})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Jeremiah 48" in detail
    assert "Jeremiah 49" in detail
    assert "1 perek" in detail
    assert "no undo" in detail
    assert await _at(client, track_id) == JEREMIAH_49


async def test_a_forward_destination_is_sent_to_the_advance_endpoint(client: httpx.AsyncClient) -> None:
    """Keeping each endpoint's name true: this one never records learning."""
    track_id = await _track_id(client, "Neviim")
    response = await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_49, "confirm": True})
    assert response.status_code == 422
    assert "advance" in response.json()["detail"]
    assert await _at(client, track_id) == JEREMIAH_44


async def test_correcting_to_where_he_already_is_writes_nothing(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (
        await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_44, "confirm": True})
    ).json()
    assert body["moved"] is False
    assert body["removed_units"] == 0
    assert body["removed_advances"] == 0
    assert await _at(client, track_id) == JEREMIAH_44


async def test_a_typed_reference_resolves_the_same_way_an_advance_does(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": JEREMIAH_49})

    body = (
        await client.put(f"/api/tracks/{track_id}/position", json={"to_ref": "Jeremiah 48", "confirm": True})
    ).json()

    assert body["track"]["at"]["ref"] == "Jeremiah 48"


async def test_a_bare_address_resolves_against_the_work_he_is_standing_in(client: httpx.AsyncClient) -> None:
    """The same rule an advance follows: a corpus track repeats "43" in several of its works."""
    track_id = await _track_id(client, "Neviim")
    body = (await client.put(f"/api/tracks/{track_id}/position", json={"to_ref": "43", "confirm": True})).json()
    assert body["track"]["at"]["ref"] == "Jeremiah 43"


async def test_an_unresolvable_reference_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.put(f"/api/tracks/{track_id}/position", json={"to_ref": "Habakkuk 9", "confirm": True})
    assert response.status_code == 422
    assert await _at(client, track_id) == JEREMIAH_44


async def test_zero_returns_the_track_to_unopened(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": 0, "confirm": True})).json()
    assert body["track"]["actual_ordinal"] == 0
    assert body["track"]["at"] is None


async def test_giving_both_a_ref_and_an_ordinal_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.put(
        f"/api/tracks/{track_id}/position",
        json={"to_ordinal": JEREMIAH_44, "to_ref": "Jeremiah 44", "confirm": True},
    )
    assert response.status_code == 422


async def test_giving_neither_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    assert (await client.put(f"/api/tracks/{track_id}/position", json={"confirm": True})).status_code == 422


async def test_an_unknown_track_is_a_404(client: httpx.AsyncClient) -> None:
    response = await client.put(
        "/api/tracks/00000000-0000-0000-0000-000000000000/position",
        json={"to_ordinal": 1, "confirm": True},
    )
    assert response.status_code == 404


async def test_the_ceiling_retreats_with_the_position_on_a_cycle_track(client: httpx.AsyncClient) -> None:
    """After a correction the corrected position is the truth, so the rail must follow it.

    The track is advanced first on purpose: seeded, its scheduled marker sits level with its
    actual one, and the ceiling takes the larger of the two -- so correcting from there would
    leave the ceiling where the schedule holds it and prove nothing.
    """
    track_id = await _track_id(client, "Chumash")
    seeded = await _at(client, track_id)
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": seeded + 5})
    ahead = await _row(client, track_id)

    body = (
        await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": seeded + 2, "confirm": True})
    ).json()

    assert body["track"]["actual_ordinal"] == seeded + 2
    assert body["track"]["reachable_to"] < ahead["reachable_to"]


async def test_a_correction_may_cross_a_cycle_turn(client: httpx.AsyncClient) -> None:
    """Confining it to the current turn would reproduce the bug this endpoint exists to fix."""
    track_id = await _track_id(client, "Chumash")
    cycle = int((await _row(client, track_id))["cycle_length"])  # type: ignore[arg-type]
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": cycle + 2})
    assert (await _row(client, track_id))["cycle_index"] == 2

    body = (
        await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": cycle - 1, "confirm": True})
    ).json()

    assert body["track"]["actual_ordinal"] == cycle - 1
    assert body["track"]["cycle_index"] == 1


async def test_a_day_outside_the_calendar_is_a_conflict(client: httpx.AsyncClient) -> None:
    """The row a correction answers with needs the schedule, and a parsha schedule needs the
    calendar. Better to say so than to answer with a guess.

    Only the refusal is asserted, not that the correction was rolled back: in production
    ``deps.py`` wraps each request in one transaction, but this harness shares a single session
    across the request on purpose, so a rollback assertion here would be testing the harness.
    ``test_start_date.py`` covers the same situation the same way.
    """
    track_id = await _track_id(client, "Chumash")
    seeded = await _at(client, track_id)
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": seeded + 2})

    response = await client.put(
        f"/api/tracks/{track_id}/position",
        params=on(400),
        json={"to_ordinal": seeded, "confirm": True},
    )

    assert response.status_code == 409
    assert "calendar" in response.json()["detail"]


async def test_a_correction_writes_the_ledger_out_before_deleting_anything(
    client: httpx.AsyncClient, app: FastAPI, tmp_path: Path
) -> None:
    """The one destructive gesture in the app, made recoverable by the import path that exists."""
    track_id = await _track_id(client, "Neviim")
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": JEREMIAH_49})
    copy = app.dependency_overrides[safety_copy_path]()
    assert not copy.exists()

    await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_48, "confirm": True})

    # The state that has just stopped existing, not the state that replaced it.
    document = read_ledger(copy)
    assert any(record.to_ordinal == JEREMIAH_49 for record in document.advances)
    assert await _at(client, track_id) == JEREMIAH_48


async def test_a_refused_correction_writes_nothing(client: httpx.AsyncClient, app: FastAPI) -> None:
    """Only the branch that deletes takes a copy; a replay and a refusal both leave the disk alone."""
    track_id = await _track_id(client, "Neviim")
    copy = app.dependency_overrides[safety_copy_path]()

    await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_49, "confirm": True})
    await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_44, "confirm": True})
    await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_44 - 1})

    assert not copy.exists()


async def test_a_safety_copy_that_cannot_be_written_stops_the_deletion(
    client: httpx.AsyncClient, app: FastAPI, tmp_path: Path
) -> None:
    """Skipping past an unwritable backup would defeat the whole point of taking one."""
    track_id = await _track_id(client, "Neviim")
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": JEREMIAH_49})
    # A directory where the file belongs: the write raises rather than silently doing nothing.
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    app.dependency_overrides[safety_copy_path] = lambda: blocked

    response = await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_48, "confirm": True})

    assert response.status_code == 409
    assert "nothing was changed" in response.json()["detail"]
    assert await _at(client, track_id) == JEREMIAH_49
