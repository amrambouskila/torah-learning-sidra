from __future__ import annotations

import httpx
import pytest

from tests.api.conftest import on

pytestmark = pytest.mark.integration


async def test_today_groups_every_active_track_by_category(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/today")).json()
    assert [row["name_en"] for row in body["daily"]] == ["Chumash", "Neviim"]
    assert [row["name_en"] for row in body["shabbat"]] == ["Likutei Sichot"]
    assert [row["name_en"] for row in body["chavrusa"]] == ["David Hadar — Brachot"]


async def test_today_carries_the_hebrew_date_and_the_parsha(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/today")).json()
    assert body["hebrew_date"]
    assert body["parsha_en"] == ["Ki Tavo"]
    assert body["parsha_he"] == ["כי תבוא"]
    assert body["is_yom_tov"] is False


async def test_the_neviim_row_reports_the_measured_debt(client: httpx.AsyncClient) -> None:
    """Yirmiyahu 44 against a scheduled 47: three perakim owed."""
    body = (await client.get("/api/today")).json()
    neviim = next(row for row in body["daily"] if row["name_en"] == "Neviim")
    assert neviim["debt"] == 3
    assert neviim["is_behind"] is True
    assert neviim["at"]["ref"] == "Jeremiah 44"
    assert neviim["scheduled_at"]["ref"] == "Jeremiah 47"
    assert neviim["up_next"]["ref"] == "Jeremiah 45"


async def test_a_row_carries_hebrew_alongside_the_transliteration(client: httpx.AsyncClient) -> None:
    """Hebrew is primary in this app; the Latin label sits beneath it."""
    body = (await client.get("/api/today")).json()
    neviim = next(row for row in body["daily"] if row["name_en"] == "Neviim")
    assert neviim["name_he"] == "נביאים"
    assert neviim["at"]["label_he"] == "מ״ד"
    assert neviim["at"]["work_title_he"] == "he-Jeremiah"


async def test_a_row_deep_links_to_sefaria(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/today")).json()
    neviim = next(row for row in body["daily"] if row["name_en"] == "Neviim")
    assert neviim["at"]["sefaria_url"] == "https://www.sefaria.org/Jeremiah_44"


async def test_a_work_that_is_not_on_sefaria_carries_no_link(client: httpx.AsyncClient) -> None:
    """Likutei Sichot is not on Sefaria at all. No link is a normal state, not a degradation."""
    body = (await client.get("/api/today")).json()
    row = next(row for row in body["shabbat"] if row["name_en"] == "Likutei Sichot")
    assert row["up_next"]["sefaria_url"] is None


async def test_a_chavrusa_row_carries_staleness_and_no_debt(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/today", params=on(11))).json()
    row = body["chavrusa"][0]
    assert row["debt"] is None
    assert row["is_behind"] is False
    assert row["days_stale"] == 11
    assert row["chavrusa"] == "David Hadar"


async def test_a_track_that_has_not_started_shows_a_countdown(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/today")).json()
    row = next(row for row in body["shabbat"] if row["name_en"] == "Likutei Sichot")
    assert row["debt"] == 0
    assert row["starts_in_days"] == 47
    assert row["at"] is None


async def test_the_parsha_tag_appears_on_rows_in_two_categories(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/today")).json()
    tagged = [row["name_en"] for group in ("daily", "shabbat") for row in body[group] if "parsha" in row["tags"]]
    assert tagged == ["Chumash", "Likutei Sichot"]


async def test_the_clock_ticks_on_a_day_nothing_was_learned(client: httpx.AsyncClient) -> None:
    """Debt is debt: the schedule does not pause for Shabbos or Yom Tov."""
    first = (await client.get("/api/today")).json()
    later = (await client.get("/api/today", params=on(5))).json()
    debt = {body["daily"][1]["name_en"]: body["daily"][1]["debt"] for body in (first, later)}
    assert debt == {"Neviim": 8}
    assert first["daily"][1]["debt"] == 3


async def test_a_day_outside_the_calendar_snapshot_is_a_conflict_not_a_wrong_answer(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/today", params=on(400))
    assert response.status_code == 409
    assert "sidra-db calendar" in response.json()["detail"]


async def test_health_answers(client: httpx.AsyncClient) -> None:
    assert (await client.get("/health")).json() == {"status": "ok"}


async def test_a_row_names_its_own_units(client: httpx.AsyncClient) -> None:
    """The badge has to read "20 amudim behind", not "20 units behind"."""
    body = (await client.get("/api/today")).json()
    nouns = {
        row["name_en"]: (row["unit_singular"], row["unit_plural"])
        for group in ("daily", "shabbat", "chavrusa")
        for row in body[group]
    }
    assert nouns["Neviim"] == ("perek", "perakim")
    assert nouns["Chumash"] == ("aliyah", "aliyot")
    assert nouns["David Hadar — Brachot"] == ("amud", "amudim")
    assert nouns["Likutei Sichot"] == ("parsha", "parshiyos")
