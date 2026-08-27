"""The counting fold, without a database."""

from __future__ import annotations

import pytest

from sidra.catalog.granularity import Granularity
from sidra.pace.counts import CountedWork, count_scope, nouns_for
from sidra.pace.pace_scope import PaceScope
from sidra.pace.scopes_file import load_scopes, parse_scopes


def _work(**overrides: object) -> CountedWork:
    defaults: dict[str, object] = {
        "corpus_id": "neviim",
        "ref_title": "Jeremiah",
        "granularity": Granularity.PEREK,
        "shape": [10] * 52,
        "unit_count": 52,
    }
    return CountedWork(**{**defaults, **overrides})  # type: ignore[arg-type]


def _scope(**overrides: object) -> PaceScope:
    defaults: dict[str, object] = {
        "id": "x.perek",
        "scope_en": "X",
        "rule": "total",
        "granularity": "perek",
        "corpus_ids": ("neviim",),
    }
    return PaceScope(**{**defaults, **overrides})  # type: ignore[arg-type]


# --- the four rules -----------------------------------------------------------------------------


def test_total_sums_the_level_a_work_is_addressed_at() -> None:
    assert count_scope([_work(), _work(unit_count=24)], _scope(), 0) == 76


def test_parents_counts_the_level_above() -> None:
    """A Rambam work's shape IS its per-perek halachah counts, so the perek count is free."""
    works = [_work(shape=[7, 7, 3, 23, 13, 10, 8], unit_count=71)]
    assert count_scope(works, _scope(rule="parents"), 0) == 7


def test_children_counts_the_level_below() -> None:
    works = [_work(shape=[7, 7, 3], unit_count=3)]
    assert count_scope(works, _scope(rule="children"), 0) == 17


def test_aliyot_ignores_the_works_entirely() -> None:
    """The one row that is not a work read: the aliyot are stored rows."""
    assert count_scope([_work()], _scope(rule="aliyot", granularity="aliyah"), 378) == 378


def test_daf_folds_two_amudim_into_one() -> None:
    # Avodah Zarah: 152 slots, the first two empty, so 2a..76b -- 150 amudim, 75 daf.
    shape = [0 if index in {0, 1} else 7 for index in range(152)]
    works = [_work(corpus_id="bavli", shape=shape, unit_count=150)]
    assert count_scope(works, _scope(rule="daf", corpus_ids=("bavli",), granularity="daf_amud"), 0) == 75


# --- selecting ----------------------------------------------------------------------------------


def test_a_corpus_scope_takes_only_that_corpus() -> None:
    works = [_work(), _work(corpus_id="ketuvim", unit_count=150)]
    assert count_scope(works, _scope(), 0) == 52


def test_a_title_prefix_scope_takes_the_parts_of_one_work() -> None:
    """`corpus_id='mussar'` would sum six unrelated sefarim into a number nobody recognises."""
    works = [
        _work(corpus_id="chassidus", ref_title="Tanya, Part I", unit_count=53),
        _work(corpus_id="chassidus", ref_title="Tanya, Part II", unit_count=12),
        _work(corpus_id="chassidus", ref_title="Likutei Moharan", unit_count=286),
    ]
    scope = _scope(corpus_ids=(), ref_title_prefix="Tanya")
    assert count_scope(works, scope, 0) == 65


def test_excluded_titles_are_left_out() -> None:
    """Tanya's front matter is caught by the prefix but is not a perek of the Tanya."""
    works = [
        _work(ref_title="Tanya, Part I", unit_count=53),
        _work(ref_title="Tanya, Title Page", unit_count=1),
        _work(ref_title="Tanya, Approbation", unit_count=3),
    ]
    scope = _scope(corpus_ids=(), ref_title_prefix="Tanya", exclude_titles=("Title Page", "Approbation"))
    assert count_scope(works, scope, 0) == 53


def test_a_multi_corpus_perek_scope_drops_non_perek_works() -> None:
    """Tanach spans three corpora, one of which also carries the parsha cycle's stored rows."""
    works = [
        _work(corpus_id="torah", unit_count=187),
        _work(corpus_id="torah", granularity=Granularity.PARSHA, unit_count=432),
        _work(corpus_id="neviim", unit_count=380),
    ]
    scope = _scope(corpus_ids=("torah", "neviim", "ketuvim"))
    assert count_scope(works, scope, 0) == 567


# --- nouns --------------------------------------------------------------------------------------


def test_a_scope_takes_the_domains_noun_by_default() -> None:
    assert nouns_for(_scope()) == ("perek", "perakim")


def test_a_scope_may_name_its_own() -> None:
    """A daf is not a Granularity, and nothing in this app is ever learned a daf at a time."""
    scope = _scope(granularity="daf_amud", unit_singular="daf", unit_plural="daf")
    assert nouns_for(scope) == ("daf", "daf")


# --- the file -----------------------------------------------------------------------------------


def test_the_real_scope_file_parses() -> None:
    scopes = load_scopes()
    assert len(scopes) >= 18
    assert {"bavli.amud", "bavli.daf", "mishneh_torah.perek", "mishneh_torah.halakhah"} <= {s.id for s in scopes}


def test_a_duplicate_id_is_refused() -> None:
    text = """
scopes:
  - {id: a.perek, scope_en: A, rule: total, granularity: perek, corpus_ids: [neviim]}
  - {id: a.perek, scope_en: B, rule: total, granularity: perek, corpus_ids: [ketuvim]}
"""
    with pytest.raises(ValueError, match="more than once: a.perek"):
        parse_scopes(text)


def test_an_unknown_rule_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown rule"):
        _scope(rule="guess")


def test_a_scope_that_selects_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="to select anything"):
        _scope(corpus_ids=(), ref_title_prefix=None)


def test_a_half_named_noun_is_refused() -> None:
    with pytest.raises(ValueError, match="both noun forms or neither"):
        _scope(unit_singular="daf")


def test_a_folded_note_becomes_one_line() -> None:
    text = """
scopes:
  - id: a.perek
    scope_en: A
    rule: total
    granularity: perek
    corpus_ids: [neviim]
    note: >-
      one sentence
      across two lines
"""
    assert parse_scopes(text)[0].note == "one sentence across two lines"
