"""The commands that used to need a terminal.

The three slow verbs are deliberately not run here: they crawl Sefaria, read the real 19 MB
snapshot, or both. What is tested is the machinery around them -- the one job slot, the refusal
when it is already taken, and that a job which fails records why instead of vanishing into a
background task nobody is awaiting.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.deps import ledger_path, safety_copy_path
from sidra.ledger.ledger_file import read_ledger
from sidra.maintenance.job_registry import JobRegistry
from sidra.maintenance.job_state import JobState
from tests.maintenance.savepoint_factory import SavepointFactory

pytestmark = pytest.mark.integration

SEEDED_TRACKS = 4
"""The miniature sidra from the seeder tests: Neviim, Chumash, Likutei Sichot, David Hadar."""


async def _settle(client: httpx.AsyncClient, tries: int = 50) -> dict[str, object]:
    """Wait for the background job to reach a terminal state, without a fixed sleep."""
    for _ in range(tries):
        body = (await client.get("/api/maintenance/job")).json()
        if body is not None and body["state"] != JobState.RUNNING:
            return body
        await asyncio.sleep(0.02)
    raise AssertionError("the job never finished")


# --- what the screen shows before he presses anything -------------------------------------------


async def test_status_reports_both_halves_of_the_database(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/maintenance")).json()
    assert body["catalog_seeded"] is True
    assert body["ledger_seeded"] is True
    assert body["works"] > 0
    assert body["tracks"] == SEEDED_TRACKS
    assert body["advances"] > 0


async def test_status_says_when_nothing_has_been_exported_yet(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/maintenance")).json()
    assert body["ledger_exported_at"] is None
    assert body["safety_copy_at"] is None


# --- export -------------------------------------------------------------------------------------


async def test_export_writes_the_ledger_and_reports_what_it_wrote(client: httpx.AsyncClient, app: FastAPI) -> None:
    out = app.dependency_overrides[ledger_path]()

    body = (await client.post("/api/maintenance/export")).json()

    assert body["tracks"] == SEEDED_TRACKS
    assert body["advances"] > 0
    assert body["path"] == str(out)
    # Written in the form the import path accepts, not a shape of its own.
    document = read_ledger(out)
    assert len(document.tracks) == SEEDED_TRACKS


async def test_status_shows_the_export_once_one_has_happened(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/maintenance")).json()["ledger_exported_at"] is None
    await client.post("/api/maintenance/export")
    assert (await client.get("/api/maintenance")).json()["ledger_exported_at"] is not None


# --- verify -------------------------------------------------------------------------------------


async def test_verify_answers_with_the_mismatches_rather_than_an_exit_code(
    client: httpx.AsyncClient,
) -> None:
    """The CLI exits non-zero; a screen needs the sentences instead."""
    body = (await client.post("/api/maintenance/verify")).json()
    assert isinstance(body["failures"], list)
    assert body["matches"] is (len(body["failures"]) == 0)


# --- the one job slot ---------------------------------------------------------------------------


async def test_no_job_has_run_yet(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/maintenance/job")).json() is None


async def test_a_second_job_is_refused_while_one_runs(client: httpx.AsyncClient, app: FastAPI) -> None:
    """One slot, so two crawls cannot hammer Sefaria at once."""
    registry = JobRegistry()
    registry.start("refresh")
    app.state.jobs = registry

    response = await client.post("/api/maintenance/seed")

    assert response.status_code == 409
    assert "refresh job is already running" in response.json()["detail"]


async def test_the_running_job_is_readable_while_it_runs(client: httpx.AsyncClient, app: FastAPI) -> None:
    registry = JobRegistry()
    job = registry.start("refresh")
    job.step("crawling bavli", 4, 11)
    app.state.jobs = registry

    body = (await client.get("/api/maintenance/job")).json()

    assert body["kind"] == "refresh"
    assert body["state"] == JobState.RUNNING
    assert (body["phase"], body["done"], body["total"]) == ("crawling bavli", 4, 11)
    assert body["finished_at"] is None


async def test_a_job_that_fails_records_why_instead_of_vanishing(client: httpx.AsyncClient) -> None:
    """A background task nobody awaits swallows its exception; the slot must not.

    The calendar job reaches for the app's session factory before it touches the network, and this
    app has none -- so it fails immediately, with no crawl and no snapshot read.
    """
    started = await client.post("/api/maintenance/calendar", json={"start": "2026-10-01", "days": 3})
    assert started.status_code == 202
    assert started.json()["state"] == JobState.RUNNING

    finished = await _settle(client)

    assert finished["state"] == JobState.FAILED
    assert finished["error"] != ""
    assert finished["finished_at"] is not None


async def test_the_slot_frees_after_a_failure(client: httpx.AsyncClient) -> None:
    await client.post("/api/maintenance/calendar", json={"start": "2026-10-01", "days": 3})
    await _settle(client)
    # Not a 409: the previous job is over, however it ended.
    assert (await client.post("/api/maintenance/calendar", json={"start": "2026-10-01", "days": 3})).status_code == 202
    await _settle(client)


async def test_a_calendar_span_is_bounded(client: httpx.AsyncClient) -> None:
    """Twice a yearly cycle is the most one press should ever ask Sefaria for."""
    assert (await client.post("/api/maintenance/calendar", json={"start": "2026-10-01", "days": 0})).status_code == 422
    assert (
        await client.post("/api/maintenance/calendar", json={"start": "2026-10-01", "days": 900})
    ).status_code == 422


async def test_an_unknown_field_is_refused(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/maintenance/refresh", json={"include_links": True, "sneak": 1})
    assert response.status_code == 422


# --- restore, narrowly ---------------------------------------------------------------------------


async def test_restore_needs_the_word_typed_in_full(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/maintenance/restore", json={"confirm": "yes"})).status_code == 422
    assert (await client.post("/api/maintenance/restore", json={"confirm": "restore"})).status_code == 422


async def test_restore_says_so_when_there_is_no_safety_copy(client: httpx.AsyncClient) -> None:
    """Nothing has been corrected, so there is nothing to go back to."""
    response = await client.post("/api/maintenance/restore", json={"confirm": "RESTORE"})
    assert response.status_code == 409
    assert "nothing to go back to" in response.json()["detail"]


async def test_restore_puts_back_the_advance_a_correction_deleted(client: httpx.AsyncClient, app: FastAPI) -> None:
    """The whole reason this button exists, end to end."""
    rows = (await client.get("/api/tracks")).json()
    track_id = next(row["id"] for row in rows if row["name_en"] == "Neviim")
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": 125})
    assert next(r for r in (await client.get("/api/tracks")).json() if r["id"] == track_id)["actual_ordinal"] == 125

    await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": 121, "confirm": True})
    assert next(r for r in (await client.get("/api/tracks")).json() if r["id"] == track_id)["actual_ordinal"] == 121

    body = (await client.post("/api/maintenance/restore", json={"confirm": "RESTORE"})).json()

    assert body["path"] == str(app.dependency_overrides[safety_copy_path]())
    assert next(r for r in (await client.get("/api/tracks")).json() if r["id"] == track_id)["actual_ordinal"] == 125


async def test_starting_a_seed_reaches_for_the_app_s_own_session_factory(
    client: httpx.AsyncClient,
) -> None:
    """A job outlives its request, so it opens its own sessions rather than borrowing one.

    This app has no factory, so the job fails at that reach -- before it reads the 19 MB snapshot,
    which is exactly why the argument is evaluated first.
    """
    assert (await client.post("/api/maintenance/seed")).status_code == 202
    finished = await _settle(client)
    assert finished["kind"] == "seed"
    assert finished["state"] == JobState.FAILED


async def test_starting_a_refresh_builds_the_two_clients_the_crawl_needs(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The crawl itself is covered in tests/maintenance; what is under test here is the wiring.

    Stubbed at the seam because the real call pulls the catalog, and with links 656 MB of it, off
    the live Sefaria API -- which is not a thing a test suite should do.
    """
    seen: dict[str, object] = {}

    async def fake_refresh(sefaria, sync_http, path, include_links, job):  # noqa: ANN001, ANN202
        seen["include_links"] = include_links
        seen["path"] = path
        job.step("crawling torah", 1, 14)
        return "stubbed"

    monkeypatch.setattr("sidra.api.routers.maintenance.run_refresh", fake_refresh)

    assert (await client.post("/api/maintenance/refresh", json={"include_links": False})).status_code == 202
    finished = await _settle(client)

    assert finished["state"] == JobState.DONE
    assert finished["detail"] == "stubbed"
    assert seen["include_links"] is False
    assert str(seen["path"]).endswith("p1.jsonl")


async def test_a_calendar_job_is_handed_the_app_s_factory_and_the_span_he_asked_for(
    client: httpx.AsyncClient, app: FastAPI, seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wiring, with a factory actually present. The fetch itself is covered in tests/maintenance.

    Stubbed at the seam because the router builds its own HTTP client, so there is no transport to
    point at a stub -- and the real one would crawl Sefaria a day at a time.
    """
    app.state.session_factory = SavepointFactory(seeded_session)
    seen: dict[str, object] = {}

    async def fake_calendar(factory, http, start, days, job, *, pause_seconds):  # noqa: ANN001, ANN002, ANN202
        seen["factory"] = factory
        seen["start"] = start
        seen["days"] = days
        seen["pause"] = pause_seconds
        return "stubbed"

    monkeypatch.setattr("sidra.api.routers.maintenance.run_calendar", fake_calendar)

    assert (await client.post("/api/maintenance/calendar", json={"start": "2026-10-01", "days": 7})).status_code == 202
    finished = await _settle(client)

    assert finished["state"] == JobState.DONE
    assert seen["factory"] is app.state.session_factory
    assert (str(seen["start"]), seen["days"]) == ("2026-10-01", 7)
    # Throttled: Sefaria answers an unthrottled four-hundred-day crawl with 429 partway through.
    assert seen["pause"] > 0


async def test_restore_refuses_a_safety_copy_it_cannot_read(client: httpx.AsyncClient, app: FastAPI) -> None:
    """A file that exists but is not a ledger. Better to say so than to clear the ledger first."""
    copy = app.dependency_overrides[safety_copy_path]()
    copy.write_text("{ not a ledger", encoding="utf-8")

    response = await client.post("/api/maintenance/restore", json={"confirm": "RESTORE"})

    assert response.status_code == 409
    assert "not a valid ledger export" in response.json()["detail"]
