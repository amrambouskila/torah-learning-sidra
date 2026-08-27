from __future__ import annotations

import dataclasses

import pytest

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.crawl import renumber_corpus_seq
from sidra.catalog.granularity import Granularity
from sidra.catalog.work_draft import WorkDraft


def _draft(corpus_id: str, seq: int, ref_title: str) -> WorkDraft:
    return WorkDraft(
        corpus_id=corpus_id,
        corpus_seq=seq,
        index_title=ref_title,
        ref_title=ref_title,
        title_he="א",
        granularity=Granularity.PEREK,
        address_scheme=AddressScheme.FLAT,
        shape=(1,),
        labels=None,
        unit_count=1,
        source="sefaria",
    )


def test_renumbering_makes_corpus_positions_contiguous() -> None:
    """Four mussar specs each number from 1, so without this the unique constraint rejects them."""
    drafts = [
        _draft("mussar", 1, "Duties of the Heart"),
        _draft("mussar", 1, "Mesillat Yesharim"),
        _draft("mussar", 2, "Shemirat HaLashon"),
        _draft("chassidus", 1, "Tanya"),
        _draft("chassidus", 1, "Likutei Moharan"),
    ]
    renumbered = renumber_corpus_seq(drafts)
    assert [(d.corpus_id, d.corpus_seq) for d in renumbered] == [
        ("mussar", 1),
        ("mussar", 2),
        ("mussar", 3),
        ("chassidus", 1),
        ("chassidus", 2),
    ]


def test_renumbering_preserves_arrival_order_and_every_other_field() -> None:
    drafts = [_draft("mussar", 9, "A"), _draft("mussar", 3, "B")]
    renumbered = renumber_corpus_seq(drafts)
    assert [d.ref_title for d in renumbered] == ["A", "B"]
    assert renumbered[0] == dataclasses.replace(drafts[0], corpus_seq=1)


def test_renumbering_yields_unique_corpus_positions() -> None:
    drafts = [_draft("mussar", 1, f"Work{n}") for n in range(20)]
    renumbered = renumber_corpus_seq(drafts)
    assert len({(d.corpus_id, d.corpus_seq) for d in renumbered}) == len(drafts)


def test_renumbering_an_empty_list_is_empty() -> None:
    assert renumber_corpus_seq([]) == []


@pytest.mark.parametrize("corpus_id", ["torah", "neviim", "bavli"])
def test_renumbering_starts_each_corpus_at_one(corpus_id: str) -> None:
    renumbered = renumber_corpus_seq([_draft(corpus_id, 42, "X")])
    assert renumbered[0].corpus_seq == 1
