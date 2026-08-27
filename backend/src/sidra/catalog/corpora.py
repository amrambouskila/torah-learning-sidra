from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.corpus_spec import CorpusSpec
from sidra.catalog.granularity import Granularity

OVERRIDES_DIR = Path(__file__).parent / "overrides"

MISHNAH_COMMENTARY_SECTIONS = frozenset({"Rishonim on Mishnah", "Acharonim on Mishnah", "Modern Commentary on Mishnah"})
"""Sefaria's Mishnah shape carries commentary alongside the masechtos. Only the masechtos are ours."""

MISHNEH_TORAH_NON_HILCHOS = frozenset(
    {
        "Mishneh Torah, Transmission of the Oral Law",
        "Mishneh Torah, Positive Mitzvot",
        "Mishneh Torah, Negative Mitzvot",
        "Mishneh Torah, Overview of Mishneh Torah Contents",
        "Kuntres Zikah",
        "Steinsaltz Introductions to Mishneh Torah",
    }
)
"""The six nodes in the Mishneh Torah shape that are not hilchos books.

Four are the Rambam's own front matter -- his introduction and mitzvah lists -- which would
insert 805 units ahead of Yesodei HaTorah. Kuntres Zikah and the Steinsaltz introductions are
not the Rambam at all. Excluding all six leaves the 84 hilchos books, 15,143 halachos.
"""


SHULCHAN_ARUCH_NON_SIMANIM = frozenset(
    {
        "Shulchan Arukh, Introduction",
        "Shulchan Arukh, Even HaEzer, Seder HaGet",
        "Shulchan Arukh, Even HaEzer, Seder Halitzah",
    }
)
"""The three nodes in the Shulchan Aruch shape that are not simanim.

Seder HaGet and Seder Halitzah are appendices to Even HaEzer -- the procedural order for writing
a get and for chalitzah -- each a single undivided node rather than a siman anybody learns one a
day. Counting them put the corpus at 1,707 against the measured 1,705 (OC 697, YD 403, EH 178,
CM 427), and inserted two phantom units between Even HaEzer and Choshen Mishpat.
"""


@lru_cache(maxsize=1)
def ketuvim_order() -> tuple[str, ...]:
    """The traditional printed order, which differs from Sefaria's placement of Koheles."""
    return _order_file("ketuvim_order.yaml")


@lru_cache(maxsize=1)
def shulchan_aruch_order() -> tuple[str, ...]:
    """Orach Chaim first. Sefaria's shape returns the chalakim alphabetically."""
    return _order_file("shulchan_aruch_order.yaml")


def _order_file(name: str) -> tuple[str, ...]:
    payload = yaml.safe_load((OVERRIDES_DIR / name).read_text(encoding="utf-8"))
    return tuple(payload["order"])


def corpora() -> tuple[CorpusSpec, ...]:
    """Every corpus whose units are derivable from a shape array.

    Chumash's parshiyos and aliyot, the named-label works and the parsha-weekly works are not here:
    they carry data no count can produce, and have their own ingesters.
    """
    return (
        CorpusSpec(
            corpus_id="torah",
            shape_path="Tanakh/Torah",
            granularity=Granularity.PEREK,
            address_scheme=AddressScheme.FLAT,
        ),
        CorpusSpec(
            corpus_id="neviim",
            shape_path="Tanakh/Prophets",
            granularity=Granularity.PEREK,
            address_scheme=AddressScheme.FLAT,
        ),
        CorpusSpec(
            corpus_id="ketuvim",
            shape_path="Tanakh/Writings",
            granularity=Granularity.PEREK,
            address_scheme=AddressScheme.FLAT,
            order_override=ketuvim_order(),
        ),
        CorpusSpec(
            corpus_id="mishnah",
            shape_path="Mishnah",
            granularity=Granularity.PEREK,
            address_scheme=AddressScheme.FLAT,
            exclude_sections=MISHNAH_COMMENTARY_SECTIONS,
        ),
        CorpusSpec(
            corpus_id="bavli",
            shape_path="Talmud/Bavli",
            granularity=Granularity.DAF_AMUD,
            address_scheme=AddressScheme.DAF_AMUD,
            # The shape also carries Minor Tractates, Guides and Tziyyun LeNefesh Chayyah.
            include_section_prefix="Seder ",
        ),
        CorpusSpec(
            corpus_id="mishneh_torah",
            shape_path="Halakhah/Mishneh Torah",
            granularity=Granularity.HALAKHAH,
            address_scheme=AddressScheme.NESTED,
            exclude_titles=MISHNEH_TORAH_NON_HILCHOS,
        ),
        CorpusSpec(
            corpus_id="shulchan_aruch",
            shape_path="Halakhah/Shulchan Arukh",
            granularity=Granularity.SIMAN,
            address_scheme=AddressScheme.FLAT,
            exclude_titles=SHULCHAN_ARUCH_NON_SIMANIM,
            expand_complex=True,
            order_override=shulchan_aruch_order(),
        ),
    )


def single_works() -> tuple[CorpusSpec, ...]:
    """Works that are their own corpus entry -- mussar, chassidus and midrash.

    Each is one shape call on the work's own title. Several are complex and expand into their
    parts: Duties of the Heart into treatises, Tanya into its five chalakim, Shemirat HaLashon into
    its two books. Orchot Tzadikim is absent because its gates need names the shape does not carry;
    it has its own ingester.

    ``corpus_seq`` is renumbered per corpus by the crawl, since several specs share a corpus_id.
    """
    return (
        CorpusSpec(
            corpus_id="mussar",
            shape_path="Duties of the Heart",
            granularity=Granularity.PEREK,
            address_scheme=AddressScheme.FLAT,
            expand_complex=True,
        ),
        CorpusSpec(
            corpus_id="mussar",
            shape_path="Mesillat Yesharim",
            granularity=Granularity.PEREK,
            address_scheme=AddressScheme.FLAT,
        ),
        CorpusSpec(
            corpus_id="mussar",
            shape_path="Shemirat HaLashon",
            granularity=Granularity.PEREK,
            address_scheme=AddressScheme.FLAT,
            expand_complex=True,
        ),
        CorpusSpec(
            corpus_id="mussar",
            shape_path="Sha'arei Teshuvah",
            granularity=Granularity.OS,
            address_scheme=AddressScheme.NESTED,
        ),
        CorpusSpec(
            corpus_id="chassidus",
            shape_path="Likutei Moharan",
            granularity=Granularity.TORAH_SECTION,
            address_scheme=AddressScheme.NESTED,
        ),
        CorpusSpec(
            # Tinyana is a separate index; the Part I shape does not include it.
            corpus_id="chassidus",
            shape_path="Likutei Moharan, Part II",
            granularity=Granularity.TORAH_SECTION,
            address_scheme=AddressScheme.NESTED,
        ),
        CorpusSpec(
            corpus_id="chassidus",
            shape_path="Tanya",
            granularity=Granularity.PEREK,
            address_scheme=AddressScheme.FLAT,
            expand_complex=True,
        ),
        CorpusSpec(
            corpus_id="midrash",
            shape_path="Bereshit Rabbah",
            granularity=Granularity.PARAGRAPH,
            address_scheme=AddressScheme.NESTED,
        ),
    )


ORCHOT_TZADIKIM = "Orchot Tzadikim"
"""Ingested separately: its 28 gates need names the shape does not carry."""
