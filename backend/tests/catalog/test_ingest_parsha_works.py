from __future__ import annotations

import pytest

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.ingest_parsha_works import (
    PARSHIYOS_PER_YEAR,
    build_parsha_work_drafts,
    parsha_work_specs,
)
from sidra.catalog.resolve import unit_at

NAMES_EN = tuple(f"Parsha{n}" for n in range(1, PARSHIYOS_PER_YEAR + 1))
NAMES_HE = tuple(f"פרשה{n}" for n in range(1, PARSHIYOS_PER_YEAR + 1))


def test_three_parsha_weekly_works_are_specified() -> None:
    specs = parsha_work_specs()
    assert [s.ref_title for s in specs] == ["Likutei Sichot", "The Midrash Says", "Covenant and Conversation"]


def test_the_two_works_absent_from_sefaria_are_marked_local() -> None:
    """Confirmed by walking the full 6,604-book table of contents: neither is on Sefaria."""
    by_title = {s.ref_title: s for s in parsha_work_specs()}
    assert by_title["Likutei Sichot"].source == "local"
    assert by_title["Likutei Sichot"].sefaria_title is None
    assert by_title["The Midrash Says"].source == "local"
    assert by_title["Covenant and Conversation"].source == "sefaria"
    assert by_title["Covenant and Conversation"].sefaria_title == "Covenant and Conversation Family Edition"


def test_specs_are_cached() -> None:
    assert parsha_work_specs() is parsha_work_specs()


def test_every_work_holds_fifty_four_units_on_the_shared_spine() -> None:
    drafts = build_parsha_work_drafts(NAMES_EN, NAMES_HE)
    assert len(drafts) == 3
    assert all(d.unit_count == PARSHIYOS_PER_YEAR for d in drafts)
    assert all(d.corpus_id == "parsha_weekly" for d in drafts)
    assert all(d.address_scheme is AddressScheme.FLAT for d in drafts)


def test_units_resolve_to_the_parsha_names() -> None:
    draft = build_parsha_work_drafts(NAMES_EN, NAMES_HE)[0]
    unit = unit_at(
        draft.ref_title,
        draft.address_scheme,
        draft.shape,
        1,
        labels=draft.labels,
        labels_he=draft.labels_he,
    )
    assert unit.label_en == "Parsha1"
    assert unit.label_he == "פרשה1"


@pytest.mark.parametrize("short", ["en", "he"])
def test_a_spine_of_the_wrong_length_raises(short: str) -> None:
    with pytest.raises(ValueError, match="54 names"):
        build_parsha_work_drafts(
            NAMES_EN[:5] if short == "en" else NAMES_EN,
            NAMES_HE[:5] if short == "he" else NAMES_HE,
        )
