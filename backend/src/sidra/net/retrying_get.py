"""GET with bounded retry on gateway failures and transport errors.

Every upstream this project reads from -- Sefaria's shape and calendar endpoints, Hebcal's
converter and events -- answers a long sequential run with an occasional 504. A crawl makes
hundreds of calls; a year of calendar makes seven hundred. Abandoning the whole run over one
transient gateway timeout is the failure mode this exists to prevent.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from sidra.net.fetch_error import FetchError

RETRYABLE_STATUS = frozenset({429, 502, 503, 504})
"""429 belongs here with the gateway statuses: a year of calendar is ~800 sequential calls and
Hebcal rate-limits a run that long. Being told to slow down is not a reason to abandon the crawl."""

DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BACKOFF_SECONDS = 1.0
MAX_RETRY_AFTER_SECONDS = 60.0
"""A ceiling on what a Retry-After header can ask for, so one hostile value cannot hang a crawl."""


def retry_after_seconds(response: httpx.Response) -> float | None:
    """How long the server asked us to wait, when it asked in seconds and asked for something sane.

    The header also has an HTTP-date form. It is not parsed: falling back to the caller's backoff
    is correct behaviour, and a date parser here would be a second thing to get wrong.
    """
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        seconds = float(raw.strip())
    except ValueError:
        return None
    if seconds <= 0:
        return None
    return min(seconds, MAX_RETRY_AFTER_SECONDS)


async def retrying_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
) -> httpx.Response:
    """GET ``url``, retrying gateway statuses and transport errors with linear backoff.

    Returns the response untouched -- including non-retryable error statuses, which the caller
    interprets. Only exhaustion raises.
    """
    last_status: int | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.get(url, params=params)
        except httpx.TransportError as error:
            if attempt == max_attempts:
                raise FetchError(f"transport error after {attempt} attempts: {error}", url=url) from error
            await asyncio.sleep(backoff_seconds * attempt)
            continue

        if response.status_code not in RETRYABLE_STATUS:
            return response

        last_status = response.status_code
        if attempt < max_attempts:
            asked = retry_after_seconds(response)
            await asyncio.sleep(backoff_seconds * attempt if asked is None else asked)

    raise FetchError(f"HTTP {last_status} after {max_attempts} attempts", url=url)
