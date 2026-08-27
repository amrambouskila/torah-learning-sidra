"""The Rambam's order, collapsed into the masechtos it actually asks for."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from sidra.db.models import Work
from sidra.sequence.dominance import Dominance


@dataclass(slots=True)
class Stage:
    """A run of consecutive hilchos books learned against one masechta.

    A book with no masechta of its own does not start a stage -- it **joins the one already
    running**. That is Amram's rule and the reason the feature exists: the Rambam goes Avoda Zara
    then Teshuvah, Teshuvah has no masechta, so the Gemara stays on Avodah Zarah until Kriyas
    Shema brings Berakhot.
    """

    masechta: str | None
    dominance: Dominance | None
    works: list[Work] = field(default_factory=list)

    @property
    def halachos(self) -> int:
        return sum(work.unit_count for work in self.works)


def stages_from(works: Sequence[Work], found: dict[str, Dominance | None]) -> list[Stage]:
    """Walk the books in order, collapsing each run that shares a masechta into one stage."""
    out: list[Stage] = []
    for work in works:
        here = found.get(work.ref_title)
        open_stage = out[-1] if out else None

        if here is None:
            # No masechta of its own: it belongs to whatever is already running.
            if open_stage is None:
                out.append(Stage(masechta=None, dominance=None, works=[work]))
            else:
                open_stage.works.append(work)
            continue

        if open_stage is not None and open_stage.masechta == here.masechta:
            open_stage.works.append(work)
            continue

        # A run that never found a masechta takes the first one that turns up, because that is the
        # masechta it was waiting for.
        if open_stage is not None and open_stage.masechta is None:
            open_stage.masechta, open_stage.dominance = here.masechta, here
            open_stage.works.append(work)
            continue

        out.append(Stage(masechta=here.masechta, dominance=here, works=[work]))
    return out
