from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration


async def _row(client: httpx.AsyncClient, name: str) -> dict[str, object]:
    rows = (await client.get("/api/roadmap")).json()
    return next(row for row in rows if row["name_en"] == name)


async def test_the_roadmap_covers_every_active_track(client: httpx.AsyncClient) -> None:
    rows = (await client.get("/api/roadmap")).json()
    assert {row["name_en"] for row in rows} == {"Chumash", "Neviim", "Likutei Sichot", "David Hadar — Brachot"}


async def test_a_projection_is_arithmetic_over_what_remains(client: httpx.AsyncClient) -> None:
    row = await _row(client, "Neviim")
    assert row["total"] == 128
    assert row["actual_ordinal"] == 120
    assert row["units_remaining"] == 8
    assert row["rate_per_day"] == 1
    assert row["projected_finish"] == "2026-09-01"


async def test_a_weekly_track_projects_on_the_same_daily_clock(client: httpx.AsyncClient) -> None:
    """A rate of one a week is one seventh of a unit a day, so every track projects together."""
    row = await _row(client, "Likutei Sichot")
    assert row["rate_per_day"] == pytest.approx(1 / 7)
    assert row["units_remaining"] == 54


async def test_the_debt_rides_along_with_the_projection(client: httpx.AsyncClient) -> None:
    assert (await _row(client, "Neviim"))["debt"] == 3


async def test_a_chavrusa_track_carries_no_debt_in_the_roadmap(client: httpx.AsyncClient) -> None:
    assert (await _row(client, "David Hadar — Brachot"))["debt"] == 0


async def test_the_yearly_cycle_rate_is_the_pace_explorers_number(client: httpx.AsyncClient) -> None:
    """How many units a day a full cycle in a year would take -- the view Amram asked for."""
    assert (await _row(client, "Neviim"))["yearly_cycle_rate"] == pytest.approx(128 / 365)
    assert (await _row(client, "Likutei Sichot"))["yearly_cycle_rate"] == pytest.approx(54 / 365)


async def test_the_roadmap_refuses_a_day_outside_the_calendar(client: httpx.AsyncClient) -> None:
    from tests.api.conftest import on

    assert (await client.get("/api/roadmap", params=on(400))).status_code == 409


async def test_a_row_names_the_work_it_projects_and_the_body_it_belongs_to(
    client: httpx.AsyncClient,
) -> None:
    """A track named "Gemara" that holds one masechta projects that masechta. Saying only "Gemara"
    overclaims by a factor of thirty-five, so the row carries both scales."""
    rows = (await client.get("/api/roadmap")).json()
    brachot = next(row for row in rows if row["name_en"] == "David Hadar — Brachot")

    assert brachot["work_ref_title"] == "Berakhot"
    assert brachot["corpus_en"] == "Talmud Bavli"
    assert brachot["corpus_total"] > brachot["total"]
    assert brachot["corpus_years"] > 0


async def test_a_track_that_already_is_its_whole_body_offers_no_second_scale(
    client: httpx.AsyncClient,
) -> None:
    """Neviim runs the whole corpus, and the Chumash is the only aliyah work there is."""
    rows = (await client.get("/api/roadmap")).json()
    for name in ("Neviim", "Chumash"):
        row = next(item for item in rows if item["name_en"] == name)
        assert row["corpus_en"] is None, name
        assert row["corpus_years"] is None, name
