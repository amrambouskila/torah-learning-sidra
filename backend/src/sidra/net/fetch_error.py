from __future__ import annotations


class FetchError(Exception):
    """Raised when an HTTP fetch fails after exhausting its retries."""

    def __init__(self, message: str, *, url: str) -> None:
        super().__init__(message)
        self.url = url
