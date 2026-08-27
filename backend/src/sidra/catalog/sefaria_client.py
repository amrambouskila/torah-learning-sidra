from __future__ import annotations

from typing import Any

import httpx

from sidra.catalog.sefaria_error import SefariaError
from sidra.net.fetch_error import FetchError
from sidra.net.retrying_get import DEFAULT_BACKOFF_SECONDS, DEFAULT_MAX_ATTEMPTS, retrying_get


class SefariaClient:
    """Thin async wrapper over the Sefaria API.

    Sefaria answers unknown refs with HTTP 200 and an ``{"error": ...}`` body, so every response is
    inspected regardless of status code. Callers pass unprefixed paths: ``shape("Tanakh/Prophets")``.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds

    async def _fetch(self, url: str) -> httpx.Response:
        """GET with bounded retry, reported as a Sefaria failure rather than a bare transport one."""
        try:
            return await retrying_get(
                self._client,
                url,
                max_attempts=self._max_attempts,
                backoff_seconds=self._backoff_seconds,
            )
        except FetchError as error:
            raise SefariaError(str(error), url=error.url) from error

    async def _get(self, path: str) -> object:
        url = f"{self._base_url}/{path}"
        response = await self._fetch(url)
        if response.status_code != httpx.codes.OK:
            raise SefariaError(f"HTTP {response.status_code} from Sefaria", url=url)
        payload = response.json()
        if isinstance(payload, dict) and "error" in payload:
            raise SefariaError(str(payload["error"]), url=url)
        return payload

    async def shape(self, path: str) -> list[dict[str, Any]]:
        """Fetch a shape. ``path`` carries no ``shape/`` prefix -- this method adds it."""
        url = f"{self._base_url}/shape/{path}"
        payload = await self._get(f"shape/{path}")
        if not isinstance(payload, list):
            raise SefariaError(f"shape response was not a list, got {type(payload).__name__}", url=url)
        return payload

    async def index(self, title: str) -> dict[str, Any]:
        """Fetch an index. This endpoint resolves alt-struct titles; the raw one does not."""
        return self._expect_object(await self._get(f"index/{title}"), f"index/{title}")

    async def raw_index(self, title: str) -> dict[str, Any]:
        """The v2 raw index -- the only endpoint carrying ``schema.titles``, the alias source."""
        path = f"v2/raw/index/{title}"
        return self._expect_object(await self._get(path), path)

    async def text(self, ref: str) -> dict[str, Any]:
        return self._expect_object(await self._get(f"texts/{ref}"), f"texts/{ref}")

    def _expect_object(self, payload: object, path: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SefariaError(f"expected a JSON object, got {type(payload).__name__}", url=f"{self._base_url}/{path}")
        return payload
