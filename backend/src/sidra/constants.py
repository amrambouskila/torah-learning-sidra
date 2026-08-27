from __future__ import annotations

SEFARIA_BASE_URL = "https://www.sefaria.org/api"
"""Sefaria API root, without a trailing slash. Client paths are joined with a single '/'."""

AMUDIM_PER_DAF = 2
"""Every daf has an amud alef and an amud beis."""

HEBREW_BLOCK_START = "\u0590"
HEBREW_BLOCK_END = "\u05ff"
"""Unicode Hebrew block bounds.

Every Hebrew label must fall inside these plus known separators. The guard exists because
hand-written numeric character references once substituted a Cyrillic Che (U+04B4) for gershayim
and an Arabic alef (U+0673) for geresh, corrupting labels in a way that looked correct in a diff.
"""

DAYS_PER_SOLAR_YEAR = 365
"""The clock every projection runs on. The Hebrew year varies; the schedule does not."""
