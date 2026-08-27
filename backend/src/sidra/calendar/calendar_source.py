"""Fetch and parse the Hebrew calendar.

Two sources, each for what it does best. **Parsha** comes from Sefaria's ``/api/calendars``, which
accepts an arbitrary date and so makes a *dated* Chumash roadmap possible. **Hebrew date and Yom
Tov** come from Hebcal's HTTP API, which is CC-BY, needs no key, and publishes a real ``yomtov``
boolean rather than leaving it to be inferred from a title.

``@hebcal/core`` is deliberately not bundled: it is GPL-2.0, and copyleft in the frontend bundle
should be a decision rather than an accident.

Nothing here runs at request time. A year is fetched once and snapshotted.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date, timedelta
from typing import Any

import httpx

from sidra.calendar.calendar_day import CalendarDay
from sidra.calendar.parsha_index import ParshaIndex
from sidra.maintenance.progress import OnProgress
from sidra.net.retrying_get import retrying_get

SEFARIA_CALENDARS_URL = "https://www.sefaria.org/api/calendars"
HEBCAL_CONVERTER_URL = "https://www.hebcal.com/converter"
HEBCAL_EVENTS_URL = "https://www.hebcal.com/hebcal"

PARASHAT_HASHAVUA = "Parashat Hashavua"


def parse_parsha(payload: dict[str, Any], index: ParshaIndex) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Read Parashat Hashavua out of a ``/api/calendars`` payload, as real parshiyos.

    The label is resolved against the catalog's own fifty-four rather than split on its hyphen,
    because the hyphen does not mean what it looks like it means: ``Lech-Lecha`` is one parsha and
    ``Nitzavim-Vayeilech`` is two. A day that supplies no sidra -- a festival week, or a payload
    with no Parashat Hashavua at all -- yields empty tuples rather than raising: the Chumash track
    simply has no target that day, and accrues nothing.
    """
    for item in payload.get("calendar_items", []):
        if item.get("title", {}).get("en") != PARASHAT_HASHAVUA:
            continue
        return index.resolve(str(item.get("displayValue", {}).get("en", "")))
    return (), ()


def parse_hebrew_dates(payload: dict[str, Any], *, start: date | None = None) -> dict[str, dict[str, Any]]:
    """Read every Hebrew date out of a Hebcal converter payload, keyed by ISO date.

    Hebcal answers a one-day range with its *single-date* shape rather than an ``hdates`` map, so
    both are accepted. A crawl of one day is exactly what the live tests do.
    """
    hdates = payload.get("hdates")
    if isinstance(hdates, dict):
        return {str(key): value for key, value in hdates.items() if isinstance(value, dict)}
    if start is not None and "hebrew" in payload:
        return {start.isoformat(): payload}
    raise ValueError("Hebcal converter payload carries no Hebrew dates")


def parse_hebrew_date(payload: dict[str, Any]) -> str:
    """Read the Hebrew date out of a Hebcal converter payload."""
    hebrew = str(payload.get("hebrew", "")).strip()
    if not hebrew:
        raise ValueError("Hebcal converter payload carries no 'hebrew' field")
    return hebrew


TISHREI = "Tishrei"
SIMCHAT_TORAH_DAY = {True: 23, False: 22}
"""23 Tishrei in the diaspora, 22 in Israel where it shares the day with Shmini Atzeret."""


def is_simchat_torah(payload: dict[str, Any], *, diaspora: bool) -> bool:
    """Whether a Hebcal converter payload is Simchat Torah.

    Read off the numbered Hebrew date rather than a festival title, for the same reason Yom Tov is:
    a title is English and can change, while 23 Tishrei cannot.
    """
    return str(payload.get("hm", "")) == TISHREI and payload.get("hd") == SIMCHAT_TORAH_DAY[diaspora]


def close_the_cycle(days: list[CalendarDay], simchat_torah: date, final: tuple[str, str]) -> list[CalendarDay]:
    """Add V'Zot HaBerachah to the week that reads it.

    Sefaria never names it: it is read on Simchat Torah, which is never a Shabbos in the diaspora,
    so it is never an upcoming sidra. Without this a cycle bills fifty-three parshiyos and the
    Chumash falls a whole parsha behind the shul every year, for good.

    It joins the week that already carries Bereshit, which is exactly what happens in shul on
    Simchat Torah -- the Torah is finished and begun again in one morning -- so the week becomes a
    combined one and bills both, through the same path Nitzavim-Vayeilech already takes.
    """
    here = next((day for day in days if day.civil_date == simchat_torah), None)
    if here is None or not here.parsha_en:
        return days
    if final[0] in here.parsha_en:
        return days
    week = here.parsha_en
    return [
        replace(day, parsha_en=(final[0], *day.parsha_en), parsha_he=(final[1], *day.parsha_he))
        if day.parsha_en == week
        else day
        for day in days
    ]


def parse_yom_tov_dates(payload: dict[str, Any]) -> set[date]:
    """Read the Yom Tov days out of a Hebcal events payload.

    Uses Hebcal's own ``yomtov`` boolean rather than matching on titles, which would miss a
    festival whose English name changed.
    """
    days: set[date] = set()
    for item in payload.get("items", []):
        if not item.get("yomtov"):
            continue
        raw = str(item.get("date", ""))[:10]
        if not raw:
            raise ValueError(f"Hebcal marked {item.get('title', '?')!r} as Yom Tov but gave it no date")
        days.add(date.fromisoformat(raw))
    return days


async def fetch_calendar_range(
    client: httpx.AsyncClient,
    start: date,
    end: date,
    index: ParshaIndex,
    *,
    diaspora: bool = True,
    pause_seconds: float = 0.0,
    on_progress: OnProgress | None = None,
) -> list[CalendarDay]:
    """Fetch every day in a range. One Sefaria call per day, plus two Hebcal calls for the span.

    ``pause_seconds`` throttles the per-day calls. Sefaria rate-limits a run of four hundred and
    answers the rest with 429, so a real crawl passes a pause and a test passes none.

    ``on_progress`` is optional and ticks once per day, which is where the time actually goes: at
    the real pause a four-hundred-day span spends over two minutes waiting before a single response
    is counted.

    Called by the snapshot job, never at request time.
    """
    if end < start:
        raise ValueError(f"end ({end}) precedes start ({start})")

    span = (end - start).days + 1
    if on_progress is not None:
        on_progress("reading the Hebrew calendar", 0, span)
    yom_tov = await _fetch_yom_tov(client, start, end, diaspora=diaspora)

    hebrew_dates = await _hebcal_converter_range(client, start, end)

    days: list[CalendarDay] = []
    simchat_torah: list[date] = []
    current = start
    while current <= end:
        if on_progress is not None:
            on_progress(f"fetching {current.isoformat()}", len(days), span)
        parsha_en, parsha_he = parse_parsha(await _sefaria_calendars(client, current, diaspora=diaspora), index)
        converter = hebrew_dates.get(current.isoformat())
        if converter is None:
            raise ValueError(f"Hebcal returned no Hebrew date for {current}")
        if is_simchat_torah(converter, diaspora=diaspora):
            simchat_torah.append(current)
        days.append(
            CalendarDay(
                civil_date=current,
                hebrew_date=parse_hebrew_date(converter),
                parsha_en=parsha_en,
                parsha_he=parsha_he,
                is_yom_tov=current in yom_tov,
            )
        )
        current += timedelta(days=1)
        if pause_seconds and current <= end:
            await asyncio.sleep(pause_seconds)

    for day in simchat_torah:
        days = close_the_cycle(days, day, index.final)
    return days


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, Any]) -> dict[str, Any]:
    """A year of calendar is ~700 sequential calls; both upstreams answer some of them with a 504."""
    response = await retrying_get(client, url, params=params)
    response.raise_for_status()
    return dict(response.json())


async def _sefaria_calendars(client: httpx.AsyncClient, on: date, *, diaspora: bool) -> dict[str, Any]:
    params = {"year": on.year, "month": on.month, "day": on.day, "diaspora": int(diaspora)}
    return await _get_json(client, SEFARIA_CALENDARS_URL, params)


async def _hebcal_converter_range(client: httpx.AsyncClient, start: date, end: date) -> dict[str, dict[str, Any]]:
    """Every Hebrew date in the range, in one call.

    A day at a time meant ~400 sequential requests for a year, and Hebcal answers a run that long
    with 429 until it refuses outright. The range form is one request for the whole span.
    """
    params = {"cfg": "json", "start": start.isoformat(), "end": end.isoformat(), "g2h": 1}
    payload = await _get_json(client, HEBCAL_CONVERTER_URL, params)
    return parse_hebrew_dates(payload, start=start)


async def _fetch_yom_tov(client: httpx.AsyncClient, start: date, end: date, *, diaspora: bool) -> set[date]:
    days: set[date] = set()
    for year in range(start.year, end.year + 1):
        params = {"v": 1, "cfg": "json", "maj": "on", "year": year, "i": "off" if diaspora else "on"}
        days |= parse_yom_tov_dates(await _get_json(client, HEBCAL_EVENTS_URL, params))
    return {day for day in days if start <= day <= end}
