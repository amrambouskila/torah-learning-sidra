"""The two schedule operands agree about today and disagree about the past.

This is the whole reason ``PUT /schedule`` names them rather than picking one. Moving the origin
leaves every earlier day reading the seeded opening position, so the debt the ledger opened with
survives; shifting the opening position restates it. A lever that chose silently would rewrite a
measured fact -- Neviim opening three perakim behind -- without anyone asking it to.

Read through Stats rather than ``/api/tracks``: ``scheduled_series`` falls back to a flat
``anchor_ordinal`` for any day before the origin, where ``ledger_state`` refuses outright.
"""

from __future__ import annotations

import httpx
import pytest

from tests.api.conftest import on

pytestmark = pytest.mark.integration

OPENING_DEBT = 3
"""Jeremiah 44 against Jeremiah 47 on the seed day. Measured; see CLAUDE.md section 1."""

WINDOW = 4
"""Four days, so the window's first day is the seed day and ``debt_then`` is the opening debt."""


async def _track_id(client: httpx.AsyncClient, name: str) -> str:
    rows = (await client.get("/api/tracks")).json()
    return next(row["id"] for row in rows if row["name_en"] == name)


async def _debt_then(client: httpx.AsyncClient, name: str) -> int:
    body = (await client.get("/api/stats", params={**on(3), "window": WINDOW})).json()
    return int(next(row["debt_then"] for row in body["tracks"] if row["name_en"] == name))


async def _scheduled(client: httpx.AsyncClient, name: str) -> int:
    rows = (await client.get("/api/tracks", params=on(3))).json()
    return int(next(row["scheduled_at"]["corpus_ordinal"] for row in rows if row["name_en"] == name))


async def test_the_seeded_opening_debt_is_three(client: httpx.AsyncClient) -> None:
    """The measured fact this whole file guards, asserted before either lever touches it."""
    assert await _debt_then(client, "Neviim") == OPENING_DEBT


async def test_moving_the_origin_leaves_the_opening_debt_standing(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    before = await _scheduled(client, "Neviim")

    await client.put(f"/api/tracks/{track_id}/schedule", params=on(3), json={"started_on": on(1)["on"]})

    assert await _scheduled(client, "Neviim") == before - 1
    assert await _debt_then(client, "Neviim") == OPENING_DEBT


async def test_shifting_the_opening_position_restates_it(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    before = await _scheduled(client, "Neviim")

    await client.put(f"/api/tracks/{track_id}/schedule", params=on(3), json={"to_ordinal": before - 1})

    assert await _scheduled(client, "Neviim") == before - 1
    assert await _debt_then(client, "Neviim") == OPENING_DEBT - 1
