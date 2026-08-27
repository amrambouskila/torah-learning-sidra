"""Build a Sefaria deep link from a ref.

The app never caches Sefaria's text -- it links out. Sefaria's own canonical URL form replaces
spaces with underscores and the address colon with a dot, which is what its address bar shows and
what a reader recognises. Both this and the percent-encoded form were verified to resolve.
"""

from __future__ import annotations

SEFARIA_BASE = "https://www.sefaria.org"


def sefaria_url(ref: str) -> str:
    """``Mishneh Torah, Human Dispositions 5:8`` -> ``.../Mishneh_Torah,_Human_Dispositions_5.8``."""
    return f"{SEFARIA_BASE}/{ref.replace(' ', '_').replace(':', '.')}"
