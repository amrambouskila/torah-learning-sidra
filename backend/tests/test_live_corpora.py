"""Ingest every derivable corpus from the real Sefaria API and check the measured totals.

Marked ``live`` and excluded from CI. A fixture can encode the same wrong belief as the code that
reads it; only the real API contradicts it.

Run deliberately:  uv run pytest -m live
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from sidra.catalog.corpora import corpora
from sidra.catalog.corpus_ordinal import corpus_ordinal
from sidra.catalog.ingest import ingest_corpus
from sidra.catalog.sefaria_client import SefariaClient
from sidra.catalog.work_draft import WorkDraft
from sidra.constants import SEFARIA_BASE_URL

pytestmark = pytest.mark.live

# Measured against the live API on 2026-08-24: works, then derivable units.
EXPECTED = {
    "torah": (5, 187),
    "neviim": (21, 380),
    "ketuvim": (13, 362),
    "mishnah": (63, 525),
    "bavli": (37, 5349),
    "mishneh_torah": (84, 15143),
    "shulchan_aruch": (None, None),
}
SHULCHAN_ARUCH_CHALAKIM = {
    "Shulchan Arukh, Orach Chayim": 697,
    "Shulchan Arukh, Yoreh De'ah": 403,
    "Shulchan Arukh, Even HaEzer": 178,
    "Shulchan Arukh, Choshen Mishpat": 427,
}


@pytest.fixture(scope="session")
async def drafts() -> AsyncIterator[dict[str, list[WorkDraft]]]:
    async with httpx.AsyncClient(timeout=120.0) as http:
        client = SefariaClient(http, SEFARIA_BASE_URL)
        yield {spec.corpus_id: await ingest_corpus(client, spec) for spec in corpora()}


@pytest.mark.parametrize("corpus_id", ["torah", "neviim", "ketuvim", "mishnah", "bavli"])
def test_work_and_unit_counts_match_the_measured_totals(drafts: dict[str, list[WorkDraft]], corpus_id: str) -> None:
    works, units = EXPECTED[corpus_id]
    assert len(drafts[corpus_id]) == works
    assert sum(draft.unit_count for draft in drafts[corpus_id]) == units


def test_mishneh_torah_holds_eighty_four_hilchos_books(drafts: dict[str, list[WorkDraft]]) -> None:
    """15,143 halachos across 84 books.

    Not the 15,229 an early research report claimed -- that figure silently included Kuntres
    Zikah, which is not the Rambam. The shape's other 6 nodes are front matter and commentary.
    """
    assert len(drafts["mishneh_torah"]) == 84
    assert sum(draft.unit_count for draft in drafts["mishneh_torah"]) == 15143
    titles = [d.ref_title for d in drafts["mishneh_torah"]]
    assert "Kuntres Zikah" not in titles
    assert "Mishneh Torah, Positive Mitzvot" not in titles
    assert titles[0] == "Mishneh Torah, Foundations of the Torah"


def test_the_four_chalakim_hold_one_thousand_seven_hundred_five_simanim(
    drafts: dict[str, list[WorkDraft]],
) -> None:
    by_title = {draft.ref_title: draft.unit_count for draft in drafts["shulchan_aruch"]}
    for title, expected in SHULCHAN_ARUCH_CHALAKIM.items():
        assert by_title[title] == expected, title
    assert sum(SHULCHAN_ARUCH_CHALAKIM.values()) == 1705


def test_even_haezer_ingests_despite_its_null_title(drafts: dict[str, list[WorkDraft]]) -> None:
    """The node reports title: null with no heTitle, and its chapters are child lengths.

    Measured 2026-08-27: Sefaria no longer exposes Even HaEzer's two one-node appendices --
    Seder HaGet and Seder Halitzah -- as child works, so the crawl now yields the four chalakim
    alone. That is what the catalog wanted anyway: they are procedural orders, not simanim anybody
    learns one a day, and both `expected_counts.json` and CLAUDE.md section 1 already gate on the
    four-work, 1,705-siman shape.
    """
    titles = [draft.ref_title for draft in drafts["shulchan_aruch"]]
    assert "Shulchan Arukh, Even HaEzer" in titles
    assert titles == list(SHULCHAN_ARUCH_CHALAKIM)
    assert "Shulchan Arukh, Introduction" not in titles
    even_haezer = next(d for d in drafts["shulchan_aruch"] if d.ref_title == "Shulchan Arukh, Even HaEzer")
    assert even_haezer.title_he
    assert even_haezer.unit_count == 178


def test_ketuvim_follows_the_traditional_order_not_sefarias(drafts: dict[str, list[WorkDraft]]) -> None:
    titles = [draft.ref_title for draft in drafts["ketuvim"]]
    assert titles[0] == "Psalms"
    assert titles[-1] == "II Chronicles"
    assert titles[-1] != "Ecclesiastes"
    assert titles.index("Ecclesiastes") < titles.index("Esther")


def test_bavli_honours_the_tamid_and_nazir_traps(drafts: dict[str, list[WorkDraft]]) -> None:
    from sidra.catalog.address_scheme import AddressScheme
    from sidra.catalog.resolve import unit_at

    by_title = {draft.ref_title: draft for draft in drafts["bavli"]}
    tamid = by_title["Tamid"]
    assert unit_at(tamid.ref_title, AddressScheme.DAF_AMUD, tamid.shape, 1).addr == ("25b",)
    assert tamid.unit_count == 17

    nazir = by_title["Nazir"]
    resolved = {
        unit_at(nazir.ref_title, AddressScheme.DAF_AMUD, nazir.shape, seq).addr[0]
        for seq in range(1, nazir.unit_count + 1)
    }
    assert "33b" not in resolved
    assert nazir.unit_count == 129


def test_mishnah_shabbat_one_one_is_corpus_ordinal_seventy_six(drafts: dict[str, list[WorkDraft]]) -> None:
    """Seder Zeraim is exactly 75 perakim, which corroborates the real Mishna position."""
    mishnah = drafts["mishnah"]
    assert corpus_ordinal(mishnah, "Mishnah Shabbat", 1) == 76


def test_mishnah_excludes_commentary(drafts: dict[str, list[WorkDraft]]) -> None:
    titles = [draft.ref_title for draft in drafts["mishnah"]]
    assert not any("Bartenura" in title or " on Mishnah" in title for title in titles)
    assert len(titles) == 63


def test_every_work_carries_hebrew(drafts: dict[str, list[WorkDraft]]) -> None:
    """A silently empty title_he would pass a naive Hebrew guard vacuously."""
    for corpus_id, corpus_drafts in drafts.items():
        for draft in corpus_drafts:
            assert draft.title_he, f"{corpus_id}: {draft.ref_title} has no Hebrew title"
            assert any("֐" <= character <= "׿" for character in draft.title_he), draft.ref_title
