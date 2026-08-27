from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import httpx
import pytest

from sidra.calendar.calendar_day import CalendarDay
from sidra.calendar.calendar_source import (
    close_the_cycle,
    fetch_calendar_range,
    is_simchat_torah,
    parse_hebrew_date,
    parse_hebrew_dates,
    parse_parsha,
    parse_yom_tov_dates,
)
from sidra.calendar.parsha_index import ParshaIndex

# The catalog's parshiyos, reduced to the ones these payloads name. parse_parsha resolves against
# this rather than splitting on the hyphen, so the Hebrew it returns is the catalog's, not the
# payload's -- which is the point: one source of truth for a parsha's name.
INDEX = ParshaIndex.from_names(
    [
        ("Bereshit", "בראשית"),
        ("Ki Tavo", "כי תבוא"),
        ("Nitzavim", "נצבים"),
        ("Vayeilech", "וילך"),
        ("V'Zot HaBerachah", "וזאת הברכה"),
    ]
)

# Trimmed but faithful: the real /api/calendars payload for a Ki Tavo week.
SEFARIA_SINGLE = {
    "calendar_items": [
        {
            "title": {"en": "Parashat Hashavua", "he": "פרשת השבוע"},
            "displayValue": {"en": "Ki Tavo", "he": "כי תבוא"},
        },
        {"title": {"en": "Daf Yomi", "he": "דף יומי"}, "displayValue": {"en": "Bekhorot 29", "he": "בכורות כ״ט"}},
    ]
}
SEFARIA_COMBINED = {
    "calendar_items": [
        {
            "title": {"en": "Parashat Hashavua", "he": "פרשת השבוע"},
            "displayValue": {"en": "Nitzavim-Vayeilech", "he": "נצבים-וילך"},
        }
    ]
}
SEFARIA_NO_PARSHA = {"calendar_items": [{"title": {"en": "Daf Yomi"}, "displayValue": {"en": "Bekhorot 29"}}]}
HEBCAL_CONVERTER = {"hy": 5786, "hm": "Elul", "hd": 12, "hebrew": "י״ב בֶּאֱלוּל תשפ״ו"}


def hdates(**by_day: dict[str, object]) -> dict[str, object]:
    """A ranged converter payload. Hebcal answers a whole span in one call, keyed by ISO date."""
    return {"start": "x", "end": "y", "hdates": by_day}


HEBCAL_EVENTS = {
    "items": [
        {"date": "2026-10-03", "title": "Shmini Atzeret", "yomtov": True},
        {"date": "2026-10-04", "title": "Simchat Torah", "yomtov": True},
        {"date": "2026-10-10", "title": "Parashat Bereshit", "yomtov": False},
        {"date": "2026-12-05", "title": "Chanukah: 1 Candle"},
    ]
}


def test_a_single_parsha_week_parses() -> None:
    english, hebrew = parse_parsha(SEFARIA_SINGLE, INDEX)
    assert english == ("Ki Tavo",)
    assert hebrew == ("כי תבוא",)


def test_a_combined_week_yields_two_names() -> None:
    english, hebrew = parse_parsha(SEFARIA_COMBINED, INDEX)
    assert english == ("Nitzavim", "Vayeilech")
    assert hebrew == ("נצבים", "וילך")


def test_a_day_without_a_parsha_yields_empty_tuples() -> None:
    """A Yom Tov whose reading is not a weekly sidra simply has no target."""
    assert parse_parsha(SEFARIA_NO_PARSHA, INDEX) == ((), ())


def test_the_hebrew_date_parses() -> None:
    assert parse_hebrew_date(HEBCAL_CONVERTER) == "י״ב בֶּאֱלוּל תשפ״ו"


def test_a_converter_payload_without_a_hebrew_field_raises() -> None:
    with pytest.raises(ValueError, match="no 'hebrew' field"):
        parse_hebrew_date({"hy": 5786})


def test_yom_tov_days_come_from_the_boolean_not_the_title() -> None:
    """Matching on titles would miss a festival whose English name changed."""
    days = parse_yom_tov_dates(HEBCAL_EVENTS)
    assert days == {date(2026, 10, 3), date(2026, 10, 4)}
    assert date(2026, 10, 10) not in days
    assert date(2026, 12, 5) not in days


def test_a_combined_week_doubles_the_daily_aliyah_load() -> None:
    day = CalendarDay(
        civil_date=date(2026, 9, 1),
        hebrew_date="x",
        parsha_en=("Nitzavim", "Vayeilech"),
        parsha_he=("נצבים", "וילך"),
        is_yom_tov=False,
    )
    assert day.is_combined_parsha
    assert day.aliyot_this_week == 14


def test_a_normal_week_carries_seven_aliyot() -> None:
    day = CalendarDay(
        civil_date=date(2026, 8, 24),
        hebrew_date="x",
        parsha_en=("Ki Tavo",),
        parsha_he=("כי תבוא",),
        is_yom_tov=False,
    )
    assert not day.is_combined_parsha
    assert day.aliyot_this_week == 7


async def test_fetching_a_range_assembles_every_day() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "sefaria" in url:
            return httpx.Response(200, json=SEFARIA_SINGLE)
        if "converter" in url:
            return httpx.Response(200, json=hdates(**{f"2026-10-0{n}": HEBCAL_CONVERTER for n in (2, 3, 4, 5)}))
        return httpx.Response(200, json=HEBCAL_EVENTS)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        days = await fetch_calendar_range(client, date(2026, 10, 2), date(2026, 10, 5), INDEX)

    assert [day.civil_date.day for day in days] == [2, 3, 4, 5]
    assert all(day.parsha_en == ("Ki Tavo",) for day in days)
    assert [day.is_yom_tov for day in days] == [False, True, True, False]


async def test_an_inverted_range_raises() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))) as client:
        with pytest.raises(ValueError, match="precedes start"):
            await fetch_calendar_range(client, date(2026, 10, 5), date(2026, 10, 1), INDEX)


def test_a_dateless_yom_tov_raises() -> None:
    """Skipping it would drop a festival and quietly desynchronize the Chumash track."""
    with pytest.raises(ValueError, match="no date"):
        parse_yom_tov_dates({"items": [{"title": "Pesach I", "yomtov": True}]})


SIMCHAT_TORAH = {"hy": 5787, "hm": "Tishrei", "hd": 23, "hebrew": "כ״ג בְּתִשְׁרֵי תשפ״ז"}
FINAL = ("V'Zot HaBerachah", "וזאת הברכה")


@pytest.mark.parametrize(
    ("payload", "diaspora", "expected"),
    [
        (SIMCHAT_TORAH, True, True),
        (SIMCHAT_TORAH, False, False),
        ({"hm": "Tishrei", "hd": 22}, False, True),
        ({"hm": "Tishrei", "hd": 22}, True, False),
        ({"hm": "Nisan", "hd": 23}, True, False),
        ({}, True, False),
    ],
)
def test_simchat_torah_is_read_off_the_numbered_date(payload: dict, diaspora: bool, expected: bool) -> None:
    """Off 23 Tishrei rather than a festival title, for the same reason Yom Tov is: a title is
    English and can change, a Hebrew date cannot."""
    assert is_simchat_torah(payload, diaspora=diaspora) is expected


def _week(names_en: tuple[str, ...], names_he: tuple[str, ...], first: date) -> list[CalendarDay]:
    return [
        CalendarDay(
            civil_date=first + timedelta(days=offset),
            hebrew_date="x",
            parsha_en=names_en,
            parsha_he=names_he,
            is_yom_tov=False,
        )
        for offset in range(7)
    ]


def test_the_week_that_reads_the_last_parsha_bills_it() -> None:
    """Sefaria labels the Simchat Torah week ``Bereshit`` and never says V'Zot HaBerachah, so a
    cycle billed fifty-three parshiyos. The week becomes a combined one, which is what the morning
    actually is: the Torah finished and begun again."""
    days = _week(("Bereshit",), ("בראשית",), date(2026, 10, 4))
    closed = close_the_cycle(days, date(2026, 10, 4), FINAL)

    assert all(day.parsha_en == ("V'Zot HaBerachah", "Bereshit") for day in closed)
    assert all(day.parsha_he == ("וזאת הברכה", "בראשית") for day in closed)
    assert sum(day.parsha_count for day in closed) == 14


def test_only_the_week_holding_simchat_torah_is_touched() -> None:
    days = _week(("Noach",), ("נח",), date(2026, 10, 11)) + _week(("Bereshit",), ("בראשית",), date(2026, 10, 4))
    closed = close_the_cycle(days, date(2026, 10, 4), FINAL)
    assert [day.parsha_en for day in closed if day.civil_date.day > 10] == [("Noach",)] * 7


@pytest.mark.parametrize(
    ("simchat_torah", "week"),
    [
        (date(2026, 10, 4), ((), ())),
        (date(2026, 11, 30), (("Bereshit",), ("בראשית",))),
    ],
)
def test_a_week_with_nothing_to_close_is_left_alone(
    simchat_torah: date, week: tuple[tuple[str, ...], tuple[str, ...]]
) -> None:
    """No parsha on the day, or Simchat Torah outside the span at all."""
    days = _week(week[0], week[1], date(2026, 10, 4))
    assert close_the_cycle(days, simchat_torah, FINAL) == days


def test_closing_twice_does_not_bill_twice() -> None:
    days = _week(("Bereshit",), ("בראשית",), date(2026, 10, 4))
    once = close_the_cycle(days, date(2026, 10, 4), FINAL)
    assert close_the_cycle(once, date(2026, 10, 4), FINAL) == once


async def test_a_fetched_range_containing_simchat_torah_closes_the_cycle() -> None:
    """End to end: Sefaria calls the whole week Bereshit, Hebcal puts 23 Tishrei on 4 October, and
    the week comes back billing V'Zot HaBerachah alongside it."""
    bereshit = {
        "calendar_items": [
            {
                "title": {"en": "Parashat Hashavua", "he": "פרשת השבוע"},
                "displayValue": {"en": "Bereshit", "he": "בראשית"},
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "sefaria" in url:
            return httpx.Response(200, json=bereshit)
        if "converter" in url:
            return httpx.Response(
                200,
                json=hdates(
                    **{
                        "2026-10-03": HEBCAL_CONVERTER,
                        "2026-10-04": SIMCHAT_TORAH,
                        "2026-10-05": HEBCAL_CONVERTER,
                    }
                ),
            )
        return httpx.Response(200, json=HEBCAL_EVENTS)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        days = await fetch_calendar_range(client, date(2026, 10, 3), date(2026, 10, 5), INDEX)

    assert all(day.parsha_en == ("V'Zot HaBerachah", "Bereshit") for day in days), [d.parsha_en for d in days]
    assert sum(day.parsha_count for day in days) == 6


async def test_a_fetched_range_without_simchat_torah_bills_one_parsha() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "sefaria" in url:
            return httpx.Response(200, json=SEFARIA_SINGLE)
        if "converter" in url:
            return httpx.Response(200, json=hdates(**{"2026-10-03": HEBCAL_CONVERTER, "2026-10-04": HEBCAL_CONVERTER}))
        return httpx.Response(200, json=HEBCAL_EVENTS)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        days = await fetch_calendar_range(client, date(2026, 10, 3), date(2026, 10, 4), INDEX)

    assert all(day.parsha_en == ("Ki Tavo",) for day in days)


def test_a_converter_payload_with_no_hebrew_dates_at_all_raises() -> None:
    with pytest.raises(ValueError, match="no Hebrew dates"):
        parse_hebrew_dates({"start": "x"}, start=date(2026, 10, 4))


def test_a_one_day_range_comes_back_in_hebcals_single_date_shape() -> None:
    """Asking for one day gets the single-date payload, not an hdates map. A crawl of one day is
    exactly what the live tests do, and it used to raise."""
    assert parse_hebrew_dates(SIMCHAT_TORAH, start=date(2026, 10, 4)) == {"2026-10-04": SIMCHAT_TORAH}


def test_a_single_date_payload_without_a_start_is_still_refused() -> None:
    with pytest.raises(ValueError, match="no Hebrew dates"):
        parse_hebrew_dates(SIMCHAT_TORAH)


async def test_a_day_missing_from_the_converter_range_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "sefaria" in url:
            return httpx.Response(200, json=SEFARIA_SINGLE)
        if "converter" in url:
            return httpx.Response(200, json=hdates(**{"2026-10-03": HEBCAL_CONVERTER}))
        return httpx.Response(200, json=HEBCAL_EVENTS)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="no Hebrew date for 2026-10-04"):
            await fetch_calendar_range(client, date(2026, 10, 3), date(2026, 10, 4), INDEX)


async def test_a_pause_throttles_the_per_day_calls() -> None:
    """Sefaria 429s an unthrottled four-hundred-day crawl. The pause falls between days, never
    after the last one."""
    slept: list[float] = []

    async def record(seconds: float) -> None:
        slept.append(seconds)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "sefaria" in url:
            return httpx.Response(200, json=SEFARIA_SINGLE)
        if "converter" in url:
            return httpx.Response(200, json=hdates(**{f"2026-10-0{n}": HEBCAL_CONVERTER for n in (3, 4, 5)}))
        return httpx.Response(200, json=HEBCAL_EVENTS)

    with patch("sidra.calendar.calendar_source.asyncio.sleep", record):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await fetch_calendar_range(client, date(2026, 10, 3), date(2026, 10, 5), INDEX, pause_seconds=0.4)

    assert slept == [0.4, 0.4]
