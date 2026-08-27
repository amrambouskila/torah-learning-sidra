from __future__ import annotations

from dataclasses import dataclass
from datetime import date

ALIYOT_PER_PARSHA = 7


@dataclass(frozen=True, slots=True)
class CalendarDay:
    """One civil day, with everything the ledger needs to know about it.

    ``parsha_en`` holds two names in a combined week -- Vayakhel-Pekudei, Nitzavim-Vayeilech and
    the rest. The Chumash track then owes fourteen aliyot across seven days rather than seven.
    """

    civil_date: date
    hebrew_date: str
    parsha_en: tuple[str, ...]
    parsha_he: tuple[str, ...]
    is_yom_tov: bool

    @property
    def is_combined_parsha(self) -> bool:
        return len(self.parsha_en) > 1

    @property
    def parsha_count(self) -> int:
        """How many parshiyos this week supplies. Zero when the calendar names none."""
        return len(self.parsha_en)

    @property
    def aliyot_this_week(self) -> int:
        """Seven per parsha. A combined week doubles the daily load rather than halving the text."""
        return ALIYOT_PER_PARSHA * max(1, self.parsha_count)
