from __future__ import annotations

from datetime import date

import pytest

from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.track_kind import TrackKind
from sidra.ledger.track_spec import AliyahPosition, TrackSpec
from sidra.ledger.tracks_file import load_tracks_file, parse_tracks_file

MINIMAL = """
as_of: 2026-08-24
tags:
  - name: parsha
    name_he: פרשה
    color: "#8a6d3b"
chavrusas:
  - name: Rabbi Jacob
tracks:
  - name_en: Neviim
    name_he: נביאים
    category: daily
    kind: corpus
    corpus_id: neviim
    rate: 1
    period: day
    scheduled_ref: Jeremiah 47
    current_ref: Jeremiah 44
  - name_en: Chumash
    name_he: חומש
    category: daily
    kind: parsha_aliyah
    work_ref_title: Parashat HaShavua
    rate: 1
    period: day
    current_aliyah: {parsha: Ki Tavo, aliyah: 3}
    tags: [parsha]
  - name_en: Rabbi Jacob — Mishneh Torah
    name_he: הרב יעקב
    category: chavrusa
    kind: corpus
    corpus_id: mishneh_torah
    period: none
    chavrusa: Rabbi Jacob
    current_ref: "Mishneh Torah, Human Dispositions 5:8"
"""


def _spec(**overrides: object) -> TrackSpec:
    defaults: dict[str, object] = {
        "name_en": "Neviim",
        "name_he": "נביאים",
        "category": Category.DAILY,
        "kind": TrackKind.CORPUS,
        "period": Period.DAY,
        "rate": 1,
        "corpus_id": "neviim",
        "work_ref_title": None,
        "starts_on": None,
        "chavrusa": None,
        "tags": (),
        "scheduled_ref": None,
        "current_ref": None,
        "current_aliyah": None,
    }
    return TrackSpec(**{**defaults, **overrides})  # type: ignore[arg-type]


def test_the_minimal_file_parses() -> None:
    parsed = parse_tracks_file(MINIMAL)
    assert parsed.as_of == date(2026, 8, 24)
    assert [track.name_en for track in parsed.tracks] == [
        "Neviim",
        "Chumash",
        "Rabbi Jacob — Mishneh Torah",
    ]


def test_both_position_forms_parse() -> None:
    neviim, chumash, _ = parse_tracks_file(MINIMAL).tracks
    assert (neviim.scheduled_ref, neviim.current_ref) == ("Jeremiah 47", "Jeremiah 44")
    assert chumash.current_aliyah == AliyahPosition(parsha="Ki Tavo", aliyah=3)
    assert chumash.current_ref is None


def test_a_chavrusa_track_carries_no_period() -> None:
    track = parse_tracks_file(MINIMAL).tracks[2]
    assert track.period is Period.NONE
    assert track.category is Category.CHAVRUSA
    assert track.chavrusa == "Rabbi Jacob"


def test_rate_defaults_to_one_where_the_file_omits_it() -> None:
    assert parse_tracks_file(MINIMAL).tracks[2].rate == 1


def test_an_unknown_category_names_its_own_track() -> None:
    broken = MINIMAL.replace("category: daily\n    kind: corpus", "category: monthly\n    kind: corpus")
    with pytest.raises(ValueError, match="Neviim"):
        parse_tracks_file(broken)


def test_a_duplicate_track_name_raises() -> None:
    doubled = MINIMAL.replace("name_en: Chumash", "name_en: Neviim")
    with pytest.raises(ValueError, match="more than once: Neviim"):
        parse_tracks_file(doubled)


def test_an_undeclared_tag_raises() -> None:
    """A typo'd tag would silently drop the track out of every filtered view."""
    broken = MINIMAL.replace("tags: [parsha]", "tags: [parshah]")
    with pytest.raises(ValueError, match="parshah"):
        parse_tracks_file(broken)


def test_an_unlisted_chavrusa_raises() -> None:
    broken = MINIMAL.replace("chavrusa: Rabbi Jacob\n", "chavrusa: Reb Nobody\n")
    with pytest.raises(ValueError, match="Reb Nobody"):
        parse_tracks_file(broken)


def test_two_current_positions_are_refused() -> None:
    with pytest.raises(ValueError, match="one current position"):
        _spec(current_ref="Jeremiah 44", current_aliyah=AliyahPosition(parsha="Ki Tavo", aliyah=3))


def test_a_rate_below_one_is_refused() -> None:
    with pytest.raises(ValueError, match="rate must be at least 1"):
        _spec(rate=0)


def test_a_corpus_track_without_a_corpus_is_refused() -> None:
    with pytest.raises(ValueError, match="must name a corpus"):
        _spec(corpus_id=None)


def test_a_single_work_track_without_a_work_is_refused() -> None:
    with pytest.raises(ValueError, match="must name a work"):
        _spec(kind=TrackKind.CURATED_QUEUE, corpus_id=None, work_ref_title=None)


# --- the real file ------------------------------------------------------------------------


def test_the_real_sidra_holds_twenty_tracks() -> None:
    parsed = load_tracks_file()
    assert len(parsed.tracks) == 20
    assert parsed.as_of == date(2026, 8, 24)


def test_the_real_sidra_splits_six_daily_nine_shabbat_five_chavrusa() -> None:
    tracks = load_tracks_file().tracks
    counts = {category: sum(1 for t in tracks if t.category is category) for category in Category}
    assert counts == {Category.DAILY: 6, Category.SHABBAT: 9, Category.CHAVRUSA: 5}


def test_the_parsha_tag_spans_two_categories() -> None:
    """The point of tags: one label cutting across the three fixed categories."""
    tagged = [track for track in load_tracks_file().tracks if "parsha" in track.tags]
    assert [track.name_en for track in tagged] == [
        "Chumash",
        "Likutei Sichot",
        "The Midrash Says",
        "Covenant and Conversation",
    ]
    assert {track.category for track in tagged} == {Category.DAILY, Category.SHABBAT}


def test_the_three_parsha_weekly_works_start_at_shabbos_bereishis() -> None:
    weekly = [t for t in load_tracks_file().tracks if t.kind is TrackKind.PARSHA_WEEKLY]
    assert len(weekly) == 3
    assert {track.starts_on for track in weekly} == {date(2026, 10, 10)}


def test_every_chavrusa_track_carries_a_chavrusa_and_no_period() -> None:
    chavrusa_tracks = [t for t in load_tracks_file().tracks if t.category is Category.CHAVRUSA]
    assert all(track.chavrusa is not None for track in chavrusa_tracks)
    assert all(track.period is Period.NONE for track in chavrusa_tracks)


def test_the_two_measured_debts_are_written_into_the_file() -> None:
    """Avoda Zara 28b against 38b, Yirmiyahu 44 against 47 -- the P2 acceptance criteria."""
    by_name = {track.name_en: track for track in load_tracks_file().tracks}
    assert (by_name["Gemara"].current_ref, by_name["Gemara"].scheduled_ref) == (
        "Avodah Zarah 28b",
        "Avodah Zarah 38b",
    )
    assert (by_name["Neviim"].current_ref, by_name["Neviim"].scheduled_ref) == ("Jeremiah 44", "Jeremiah 47")


def test_the_four_unopened_sefarim_carry_no_position() -> None:
    unopened = [t.name_en for t in load_tracks_file().tracks if t.current_ref is None and t.current_aliyah is None]
    assert unopened == [
        "Shulchan Aruch",
        "Mesilat Yesharim",
        "Shmirat HaLashon",
        "Tanya",
        "Likutei Sichot",
        "The Midrash Says",
        "Covenant and Conversation",
    ]


def test_a_start_date_and_a_scheduled_position_contradict_each_other() -> None:
    """One says nothing is owed before that day; the other says a debt is already carried."""
    with pytest.raises(ValueError, match="contradict each other"):
        _spec(starts_on=date(2026, 10, 10), scheduled_ref="Jeremiah 47")


def test_a_chavrusa_track_cannot_declare_a_start_date() -> None:
    """It carries staleness, not a schedule, so the column would be silently inert."""
    with pytest.raises(ValueError, match="staleness, not a schedule"):
        _spec(starts_on=date(2026, 10, 10), period=Period.NONE)
