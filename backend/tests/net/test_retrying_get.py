from __future__ import annotations

import httpx
import pytest

from sidra.net.fetch_error import FetchError
from sidra.net.retrying_get import retry_after_seconds, retrying_get

URL = "https://example.test/thing"


async def _attempt_counter(responses: list[httpx.Response]) -> tuple[httpx.AsyncClient, list[int]]:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return responses[min(len(calls) - 1, len(responses) - 1)]

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


async def test_a_good_response_makes_one_call() -> None:
    client, calls = await _attempt_counter([httpx.Response(200, json={"ok": True})])
    async with client:
        response = await retrying_get(client, URL, backoff_seconds=0)
    assert response.json() == {"ok": True}
    assert len(calls) == 1


@pytest.mark.parametrize("status", [502, 503, 504])
async def test_a_gateway_status_retries_then_raises(status: int) -> None:
    client, calls = await _attempt_counter([httpx.Response(status)])
    async with client:
        with pytest.raises(FetchError, match=f"HTTP {status} after 4 attempts"):
            await retrying_get(client, URL, backoff_seconds=0)
    assert len(calls) == 4


async def test_a_transient_gateway_status_recovers() -> None:
    """The failure this exists for: one 504 inside a 700-call calendar year."""
    client, calls = await _attempt_counter([httpx.Response(504), httpx.Response(200, json={"ok": True})])
    async with client:
        response = await retrying_get(client, URL, backoff_seconds=0)
    assert response.status_code == 200
    assert len(calls) == 2


async def test_a_non_retryable_status_comes_back_untouched() -> None:
    """404 is the caller's to interpret, not something to hammer four times."""
    client, calls = await _attempt_counter([httpx.Response(404)])
    async with client:
        response = await retrying_get(client, URL, backoff_seconds=0)
    assert response.status_code == 404
    assert len(calls) == 1


async def test_a_transport_error_retries_then_raises() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ConnectError("no route", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FetchError, match="transport error after 4 attempts"):
            await retrying_get(client, URL, backoff_seconds=0)
    assert len(calls) == 4


async def test_a_transport_error_that_clears_recovers() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("no route", request=request)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await retrying_get(client, URL, backoff_seconds=0)
    assert response.status_code == 200
    assert len(calls) == 2


async def test_params_reach_the_request() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await retrying_get(client, URL, params={"gy": 2026, "gm": 8}, backoff_seconds=0)
    assert seen == [f"{URL}?gy=2026&gm=8"]


async def test_the_attempt_budget_is_configurable() -> None:
    client, calls = await _attempt_counter([httpx.Response(504)])
    async with client:
        with pytest.raises(FetchError, match="after 2 attempts"):
            await retrying_get(client, URL, max_attempts=2, backoff_seconds=0)
    assert len(calls) == 2


async def test_the_error_carries_the_url() -> None:
    client, _ = await _attempt_counter([httpx.Response(504)])
    async with client:
        with pytest.raises(FetchError) as excinfo:
            await retrying_get(client, URL, max_attempts=1, backoff_seconds=0)
    assert excinfo.value.url == URL


@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_a_rate_limit_is_retried_like_a_gateway_failure(status: int) -> None:
    """A year of calendar is ~800 sequential calls and Hebcal rate-limits that long a run."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200) if attempts > 1 else httpx.Response(status)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await retrying_get(client, "https://example.test/x", backoff_seconds=0.0)

    assert response.status_code == 200
    assert attempts == 2


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ({"Retry-After": "2"}, 2.0),
        ({"Retry-After": "  1.5 "}, 1.5),
        ({"Retry-After": "9999"}, 60.0),
        ({"Retry-After": "0"}, None),
        ({"Retry-After": "-3"}, None),
        ({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, None),
        ({}, None),
    ],
)
def test_retry_after_is_honoured_only_when_it_is_sane(header: dict[str, str], expected: float | None) -> None:
    assert retry_after_seconds(httpx.Response(429, headers=header)) == expected
