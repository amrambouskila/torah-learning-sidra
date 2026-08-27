from __future__ import annotations

import pytest

from sidra.catalog.ingest_aliases import local_alias_rows, local_aliases, sefaria_aliases

RAW_INDEX = {
    "schema": {
        "titles": [
            {"text": "Mishneh Torah, Human Dispositions", "lang": "en", "primary": True},
            {"text": "Rambam, De'ot", "lang": "en"},
            {"text": "משנה תורה, הלכות דעות", "lang": "he", "primary": True},
            {"text": 'רמב"ם, הלכות דעות', "lang": "he"},
            {"text": "Rambam, De'ot", "lang": "en"},
            {"text": "   ", "lang": "en"},
            "not-a-dict",
        ]
    }
}
KNOWN = {
    "Avodah Zarah",
    "Berakhot",
    "Psalms",
    "Jeremiah",
    "Mishneh Torah, Foreign Worship and Customs of the Nations",
    "Mishneh Torah, Human Dispositions",
    "Duties of the Heart",
    "Sha'arei Teshuvah",
    "Orchot Tzadikim",
    "Mesillat Yesharim",
    "Shemirat HaLashon",
    "Likutei Moharan",
    "Mishnah Shabbat",
}


def test_sefaria_aliases_are_harvested_with_their_language() -> None:
    rows = sefaria_aliases("Mishneh Torah, Human Dispositions", RAW_INDEX)
    assert {r.alias for r in rows} == {
        "Mishneh Torah, Human Dispositions",
        "Rambam, De'ot",
        "משנה תורה, הלכות דעות",
        'רמב"ם, הלכות דעות',
    }
    assert {r.lang for r in rows} == {"en", "he"}
    assert all(r.source == "sefaria" for r in rows)


def test_duplicates_blanks_and_non_dicts_are_skipped() -> None:
    rows = sefaria_aliases("X", RAW_INDEX)
    assert len(rows) == 4


def test_a_payload_without_a_schema_yields_nothing() -> None:
    assert sefaria_aliases("X", {"title": "X"}) == []


def test_amrams_own_spellings_are_present() -> None:
    aliases = dict(local_aliases())
    assert aliases["Mesechet Avoda Zara"] == "Avodah Zarah"
    assert aliases["Hilchos Daos"] == "Mishneh Torah, Human Dispositions"
    assert aliases["Brachot"] == "Berakhot"
    assert aliases["Tehilim"] == "Psalms"


def test_local_alias_rows_target_known_works() -> None:
    rows = local_alias_rows(KNOWN)
    assert all(r.source == "local" and r.lang == "en" for r in rows)
    assert any(r.alias == "Mesechet Avoda Zara" and r.ref_title == "Avodah Zarah" for r in rows)


def test_an_alias_naming_an_unknown_work_raises() -> None:
    """A typo in the YAML must fail the ingest, not vanish."""
    with pytest.raises(ValueError, match="not in the catalog"):
        local_alias_rows({"Avodah Zarah"})


def test_an_alias_resolves_to_a_work_that_exists_only_as_its_parts() -> None:
    """Duties of the Heart expands into ten treatises; no row carries the bare family name."""
    from sidra.catalog.ingest_aliases import resolve_alias_target

    parts = [
        "Duties of the Heart, Introduction of the Author",
        "Duties of the Heart, First Treatise on Unity",
        "Shemirat HaLashon, Book I, The Gate of Remembering",
    ]
    assert resolve_alias_target("Duties of the Heart", parts) == "Duties of the Heart, Introduction of the Author"
    assert resolve_alias_target("Shemirat HaLashon", parts) == "Shemirat HaLashon, Book I, The Gate of Remembering"


def test_an_exact_match_wins_over_a_prefix_match() -> None:
    from sidra.catalog.ingest_aliases import resolve_alias_target

    known = ["Duties of the Heart, First Treatise on Unity", "Duties of the Heart"]
    assert resolve_alias_target("Duties of the Heart", known) == "Duties of the Heart"


def test_a_target_matching_nothing_resolves_to_none() -> None:
    from sidra.catalog.ingest_aliases import resolve_alias_target

    assert resolve_alias_target("Nonesuch", ["Avodah Zarah"]) is None


def test_a_prefix_must_be_followed_by_a_comma() -> None:
    """'Tanya' must not silently match 'Tanya Commentary'."""
    from sidra.catalog.ingest_aliases import resolve_alias_target

    assert resolve_alias_target("Tanya", ["Tanya Commentary"]) is None
    assert resolve_alias_target("Tanya", ["Tanya, Part I; Likkutei Amarim"]) == "Tanya, Part I; Likkutei Amarim"
