from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from sidra.catalog.sefaria_client import SefariaClient
from sidra.catalog.sefaria_error import SefariaError

BASE = "https://www.sefaria.org/api"

SHAPE_OK = [{"section": "Seder Nezikin", "title": "Avodah Zarah", "length": 152, "chapters": [0, 0, 8]}]
INDEX_OK = {"title": "Deuteronomy", "alts": {"Parasha": {"nodes": []}}}
RAW_INDEX_OK = {"schema": {"titles": [{"text": "Hilchot De'ot", "lang": "en"}]}}
ERROR_BODY = {"error": "No book named 'Nonesuch'."}

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler) -> SefariaClient:
    return SefariaClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)), BASE)


def _recording(payload: object, seen: list[str]) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json=payload)

    return handler


async def test_shape_returns_the_parsed_body() -> None:
    assert await _client(_recording(SHAPE_OK, [])).shape("Talmud/Bavli") == SHAPE_OK


async def test_shape_does_not_double_prefix_the_path() -> None:
    """Callers pass 'Tanakh/Prophets'; the client adds the 'shape/' segment itself."""
    seen: list[str] = []
    await _client(_recording(SHAPE_OK, seen)).shape("Tanakh/Prophets")
    assert seen == ["/api/shape/Tanakh/Prophets"]


async def test_a_two_hundred_with_an_error_body_raises() -> None:
    """Sefaria's status codes lie. This is the whole reason the client exists."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ERROR_BODY)

    with pytest.raises(SefariaError, match="No book named"):
        await _client(handler).index("Nonesuch")


async def test_a_clean_two_hundred_does_not_raise() -> None:
    payload = await _client(_recording(INDEX_OK, [])).index("Deuteronomy")
    assert payload["title"] == "Deuteronomy"


async def test_a_real_http_error_raises_too() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(SefariaError, match="HTTP 500"):
        await _client(handler).index("Deuteronomy")


async def test_raw_index_hits_the_v2_raw_endpoint() -> None:
    """schema.titles, the alias source, lives only on the raw endpoint."""
    seen: list[str] = []
    payload = await _client(_recording(RAW_INDEX_OK, seen)).raw_index("Mishneh Torah, Human Dispositions")
    assert seen[0].startswith("/api/v2/raw/index/")
    assert payload["schema"]["titles"][0]["text"] == "Hilchot De'ot"


async def test_text_hits_the_texts_endpoint() -> None:
    seen: list[str] = []
    await _client(_recording({"ref": "Avodah Zarah 28b"}, seen)).text("Avodah Zarah 28b")
    assert seen[0].startswith("/api/texts/")


async def test_the_error_carries_the_failing_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ERROR_BODY)

    with pytest.raises(SefariaError) as excinfo:
        await _client(handler).text("Nonesuch 1:1")
    assert "texts/" in excinfo.value.url


async def test_a_shape_response_that_is_not_a_list_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "object"})

    with pytest.raises(SefariaError, match="not a list"):
        await _client(handler).shape("Talmud/Bavli")


async def test_a_trailing_slash_on_the_base_url_is_tolerated() -> None:
    seen: list[str] = []
    client = SefariaClient(
        httpx.AsyncClient(transport=httpx.MockTransport(_recording(SHAPE_OK, seen))),
        "https://www.sefaria.org/api/",
    )
    await client.shape("Mishnah")
    assert seen == ["/api/shape/Mishnah"]


async def test_an_index_response_that_is_not_an_object_raises() -> None:
    """Sefaria returning a list where an object belongs is a contract break, not a shrug."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["unexpected", "array"])

    with pytest.raises(SefariaError, match="expected a JSON object"):
        await _client(handler).index("Deuteronomy")


def _flaky(statuses: list[int], payload: object) -> Handler:
    """Return the given statuses in order, then a good response for every later call."""
    remaining = list(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        if remaining:
            return httpx.Response(remaining.pop(0), text="gateway")
        return httpx.Response(200, json=payload)

    return handler


def _fast(handler: Handler) -> SefariaClient:
    return SefariaClient(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        BASE,
        backoff_seconds=0.0,
    )


@pytest.mark.parametrize("status", [502, 503, 504])
async def test_a_gateway_failure_is_retried(status: int) -> None:
    """A full crawl makes fifteen sequential shape calls; one transient 504 must not abandon it."""
    assert await _fast(_flaky([status], SHAPE_OK)).shape("Talmud/Bavli") == SHAPE_OK


async def test_retries_are_bounded() -> None:
    with pytest.raises(SefariaError, match="after 4 attempts"):
        await _fast(_flaky([504, 504, 504, 504], SHAPE_OK)).shape("Talmud/Bavli")


async def test_a_non_retryable_status_is_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, text="boom")

    with pytest.raises(SefariaError, match="HTTP 500"):
        await _fast(handler).index("Deuteronomy")
    assert calls == 1


async def test_a_transport_error_is_retried_then_surfaces() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("connection reset")
        return httpx.Response(200, json=SHAPE_OK)

    assert await _fast(handler).shape("Mishnah") == SHAPE_OK
    assert attempts == 3


async def test_a_persistent_transport_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection reset")

    with pytest.raises(SefariaError, match="transport error after 4 attempts"):
        await _fast(handler).shape("Mishnah")
