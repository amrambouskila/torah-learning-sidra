"""The Pace Explorer over the real catalog."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_it_answers_without_a_ledger(client: httpx.AsyncClient) -> None:
    """Nothing here reads a track, so the numbers hold whatever Amram owes."""
    rows = (await client.get("/api/pace")).json()
    assert rows
    assert all("debt" not in row for row in rows)


async def test_every_row_carries_both_answers(client: httpx.AsyncClient) -> None:
    """Two knobs, not two modes: a row always says both the rate and the horizon."""
    row = (await client.get("/api/pace", params={"years": 1, "per_day": 1})).json()[0]
    assert row["per_day_for_horizon"] > 0
    assert row["years_at_rate"] > 0


async def test_the_horizon_is_a_duration_and_never_a_date(client: httpx.AsyncClient) -> None:
    """A duration cannot be misread as the Roadmap's finish line."""
    for row in (await client.get("/api/pace")).json():
        assert isinstance(row["years_at_rate"], float)
        assert "-" not in str(row["years_at_rate"])


async def _rates(client: httpx.AsyncClient, field: str, **params: float) -> dict[str, float]:
    rows = (await client.get("/api/pace", params=params)).json()
    return {row["row_id"]: row[field] for row in rows}


async def test_halving_the_horizon_doubles_the_rate(client: httpx.AsyncClient) -> None:
    one = await _rates(client, "per_day_for_horizon", years=1)
    half = await _rates(client, "per_day_for_horizon", years=0.5)
    for row_id, rate in one.items():
        assert half[row_id] == pytest.approx(rate * 2)


async def test_doubling_the_rate_halves_the_horizon(client: httpx.AsyncClient) -> None:
    one = await _rates(client, "years_at_rate", per_day=1)
    two = await _rates(client, "years_at_rate", per_day=2)
    for row_id, years in one.items():
        assert two[row_id] == pytest.approx(years / 2)


async def test_a_row_carrying_a_caveat_says_it(client: httpx.AsyncClient) -> None:
    """2,684 daf carry text; the traditional 2,711 counts daf that hold no Gemara."""
    rows = {row["row_id"]: row for row in (await client.get("/api/pace")).json()}
    assert "2,711" in (rows["bavli.daf"]["note"] or "")


@pytest.mark.parametrize(
    ("params", "why"),
    [
        ({"years": 0}, "a zero horizon would divide by zero"),
        ({"years": -1}, "a negative horizon is not a horizon"),
        ({"per_day": 0}, "a zero rate never finishes"),
        ({"years": 500}, "beyond any human horizon"),
        ({"per_day": 100000}, "beyond any human rate"),
    ],
)
async def test_a_nonsense_input_is_refused(client: httpx.AsyncClient, params: dict[str, float], why: str) -> None:
    assert (await client.get("/api/pace", params=params)).status_code == 422, why


async def test_an_empty_catalog_says_what_to_run(client: httpx.AsyncClient, seeded_session: object) -> None:
    from sidra.db.seed import clear_catalog

    await clear_catalog(seeded_session)  # type: ignore[arg-type]
    response = await client.get("/api/pace")
    assert response.status_code == 409
    assert "sidra-db seed" in response.json()["detail"]
