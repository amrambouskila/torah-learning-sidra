from __future__ import annotations

from sidra.sequence.dominance import Dominance
from sidra.sequence.masechta_map import shared_prefix
from sidra.sequence.stages import stages_from


class _Work:
    """Only what a stage reads. The real Work is a mapped model and needs a session."""

    def __init__(self, ref_title: str, unit_count: int) -> None:
        self.ref_title = ref_title
        self.unit_count = unit_count


def _found(masechta: str) -> Dominance:
    return Dominance(masechta=masechta, links=100, share=0.6, runner_up="Other", runner_up_links=20)


# The Rambam's real order out of Hilchos Avoda Zara, with the masechtos Ein Mishpat gives each.
RAMBAM = [
    _Work("Foreign Worship", 60),
    _Work("Repentance", 41),
    _Work("Reading the Shema", 26),
    _Work("Prayer and the Priestly Blessing", 121),
    _Work("Tefillin, Mezuzah and the Torah Scroll", 111),
    _Work("Fringes", 26),
    _Work("Blessings", 89),
]
MAP = {
    "Foreign Worship": _found("Avodah Zarah"),
    "Repentance": None,
    "Reading the Shema": _found("Berakhot"),
    "Prayer and the Priestly Blessing": _found("Berakhot"),
    "Tefillin, Mezuzah and the Torah Scroll": _found("Menachot"),
    "Fringes": _found("Menachot"),
    "Blessings": _found("Berakhot"),
}


def test_a_section_with_no_masechta_does_not_move_him() -> None:
    """Amram's rule, and the whole point: the Rambam goes Avoda Zara then Teshuvah, Teshuvah has
    no masechta of its own, so the Gemara stays on Avodah Zarah until Kriyas Shema brings
    Berakhot."""
    stages = stages_from(RAMBAM, MAP)
    assert stages[0].masechta == "Avodah Zarah"
    assert [work.ref_title for work in stages[0].works] == ["Foreign Worship", "Repentance"]
    assert stages[1].masechta == "Berakhot"


def test_consecutive_sections_sharing_a_masechta_are_one_stage() -> None:
    stages = stages_from(RAMBAM, MAP)
    berakhot = stages[1]
    assert [work.ref_title for work in berakhot.works] == [
        "Reading the Shema",
        "Prayer and the Priestly Blessing",
    ]
    assert berakhot.halachos == 26 + 121


def test_the_code_returning_to_a_masechta_is_a_separate_stage() -> None:
    """Hilchos Brachos comes back to Berakhot long after Kriyas Shema. Whether to learn it again
    is his call, so it is shown rather than folded away."""
    stages = stages_from(RAMBAM, MAP)
    assert [stage.masechta for stage in stages] == ["Avodah Zarah", "Berakhot", "Menachot", "Berakhot"]


def test_a_run_that_opens_with_no_masechta_adopts_the_first_one_that_turns_up() -> None:
    """Standing inside Teshuvah, the stage he is in is the one Kriyas Shema is about to name."""
    works = [_Work("Repentance", 41), _Work("Reading the Shema", 26)]
    stages = stages_from(works, MAP)
    assert len(stages) == 1
    assert stages[0].masechta == "Berakhot"
    assert stages[0].halachos == 67


def test_a_code_that_never_names_a_masechta_is_one_nameless_stage() -> None:
    works = [_Work("Repentance", 41), _Work("The Order of Prayer", 3)]
    stages = stages_from(works, {"Repentance": None, "The Order of Prayer": None})
    assert len(stages) == 1
    assert stages[0].masechta is None
    assert stages[0].halachos == 44


def test_nothing_ahead_is_no_stages() -> None:
    assert stages_from([], MAP) == []


def test_the_shared_prefix_is_what_one_query_can_fetch() -> None:
    assert shared_prefix(["Mishneh Torah, Sabbath", "Mishneh Torah, Eruvin"]) == "Mishneh Torah, "
    assert shared_prefix(["Berakhot", "Shabbat"]) == ""
    assert shared_prefix([]) == ""
