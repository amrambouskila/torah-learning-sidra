"""Whether one masechta is what a hilchos book is actually about."""

from __future__ import annotations

from dataclasses import dataclass

MIN_SHARE = 0.25
MIN_RATIO = 1.5
"""A masechta counts as this section's source only if it both holds a quarter of the citations and
leads the runner-up by half again.

Measured against all 84 hilchos books. The ratio is what does the work: Teshuvah's leader is Yoma
at 1.19x Sanhedrin, and Deos' is Berakhot at 1.19x Shabbos -- neither is a masechta *about* that
subject, and Amram's rule is that such a section does not move him off the masechta he is on. By
contrast Hilchos Avoda Zara leads at 1.56x and Kriyas Shema at 11.8x. The share floor catches the
opposite case, where a leader wins a thin field on few citations.

A section split evenly between two masechtos also fails, and that is correct: Hilchos Maachalos
Assuros is Chullin 318 against Avodah Zarah 288, and neither one owns it.
"""


@dataclass(frozen=True, slots=True)
class Dominance:
    """The masechta a hilchos book draws on, when one clearly does."""

    masechta: str
    links: int
    share: float
    runner_up: str | None
    runner_up_links: int


def dominant(counts: dict[str, int]) -> Dominance | None:
    """The masechta this section is about, or None when no single one owns it."""
    if not counts:
        return None
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    (top, links), rest = ranked[0], ranked[1:]
    second, second_links = rest[0] if rest else (None, 0)

    total = sum(counts.values())
    if links / total < MIN_SHARE:
        return None
    if second_links and links < MIN_RATIO * second_links:
        return None
    return Dominance(masechta=top, links=links, share=links / total, runner_up=second, runner_up_links=second_links)
