from __future__ import annotations

CORPUS_IDS = frozenset(
    {
        "torah",
        "neviim",
        "ketuvim",
        "mishnah",
        "bavli",
        "mishneh_torah",
        "shulchan_aruch",
        "mussar",
        "chassidus",
        "midrash",
        "parsha_weekly",
    }
)
"""The canonical corpus vocabulary, declared once so no ingester can invent a variant."""
