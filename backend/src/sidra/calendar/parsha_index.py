"""Resolve what Sefaria's calendar calls a week against the fifty-four real parshiyos."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

COMBINED_SEPARATOR = "-"

_APOSTROPHES = re.compile(r"['’]")
_SEPARATORS = re.compile(r"[\s\-]+")


def parsha_key(name: str) -> str:
    """A comparison key that ignores how a name is punctuated.

    Sefaria writes the same parsha differently in different places -- ``Lech-Lecha`` in the
    calendar against ``Lech Lecha`` in the index. A hyphen and a space are the same separator; an
    apostrophe is not a separator at all, so ``Ha'Azinu`` and ``Haazinu`` are one name while
    ``Lech Lecha`` stays two words.
    """
    return _SEPARATORS.sub(" ", _APOSTROPHES.sub("", name)).strip().casefold()


@dataclass(frozen=True, slots=True)
class ParshaIndex:
    """The fifty-four parshiyos, keyed for lookup, taken from the catalog rather than written out.

    A calendar week is one of exactly three things, and only this index can tell them apart:

    * one parsha -- ``Ki Tavo``, and also ``Lech-Lecha``, whose name merely contains a hyphen;
    * two, a genuinely combined reading -- ``Nitzavim-Vayeilech``, ``Achrei Mot-Kedoshim``;
    * none at all -- ``Rosh Hashana I``, ``Sukkot I``, ``Shmini Atzeret``, which displace the
      weekly sidra rather than supplying one.

    Splitting on the hyphen alone cannot separate the first case from the second, and nothing at
    all separates the third. Both were live bugs: ``Lech-Lecha`` billed two parshiyos, and every
    festival week billed one that was never read.
    """

    by_key: dict[str, tuple[str, str]]
    """Comparison key -> the catalog's own (label_en, label_he) for that parsha."""

    in_order: tuple[tuple[str, str], ...]
    """The cycle in reading order, Bereshit first. Only the last one is used, and it is used
    because it is the last rather than because of its name."""

    @classmethod
    def from_names(cls, names: Iterable[tuple[str, str]]) -> ParshaIndex:
        """Build from (label_en, label_he) pairs in reading order, whichever end they arrive from."""
        ordered = tuple(names)
        return cls(
            by_key={parsha_key(label_en): (label_en, label_he) for label_en, label_he in ordered},
            in_order=ordered,
        )

    @property
    def final(self) -> tuple[str, str]:
        """The parsha that closes the cycle -- V'Zot HaBerachah, which the calendar never names.

        It is read on Simchat Torah, 23 Tishrei, which in the diaspora can never fall on Shabbos,
        so it is never anybody's *upcoming* sidra and Sefaria's Parashat Hashavua never says it.
        Only fifty-three of the fifty-four ever appear.
        """
        return self.in_order[-1]

    def resolve(self, display_en: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Read a calendar label as the parshiyos it actually supplies.

        Returns the English and Hebrew names as parallel tuples, both empty when the week supplies
        no sidra. The Hebrew comes from the catalog, so it is Sefaria's own, never assembled here.
        """
        cleaned = display_en.strip()
        if not cleaned:
            return (), ()

        whole = self.by_key.get(parsha_key(cleaned))
        if whole is not None:
            return (whole[0],), (whole[1],)

        if COMBINED_SEPARATOR not in cleaned:
            return (), ()

        head, _, tail = cleaned.partition(COMBINED_SEPARATOR)
        first, second = self.by_key.get(parsha_key(head)), self.by_key.get(parsha_key(tail))
        if first is None or second is None:
            return (), ()
        return (first[0], second[0]), (first[1], second[1])
