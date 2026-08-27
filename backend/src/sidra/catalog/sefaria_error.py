from __future__ import annotations

from sidra.net.fetch_error import FetchError


class SefariaError(FetchError):
    """Raised when Sefaria reports an error, including inside an HTTP 200 body."""
