"""The P1 acceptance gate.

Crawls the real Sefaria API, seeds a real Postgres, and asserts Amram's actual positions. Every
number here was measured; if one stops holding, the ingester is wrong, not the number.

Marked ``live`` because it takes a couple of minutes and moves real data. It is the test that says
P1 is done.

Run:  uv run pytest -m live -k reference_values
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.bavli_amudim import real_amudim
from sidra.catalog.corpus_ordinal import corpus_ordinal
from sidra.catalog.crawl import crawl_catalog
from sidra.catalog.resolve import unit_at
from sidra.catalog.sefaria_client import SefariaClient
from sidra.constants import HEBREW_BLOCK_END, HEBREW_BLOCK_START, SEFARIA_BASE_URL
from sidra.db.models import LearnableUnit, TitleAlias, Work
from sidra.db.seed import seed_from_snapshot
from sidra.expected_counts import check_catalog, load_expected_counts

pytestmark = pytest.mark.live

# Amram's real positions on 2026-08-24. Every one must resolve to a catalog unit.
SEED_REFS = {
    "Avodah Zarah 28b": ("bavli", "Avodah Zarah"),
    "Avodah Zarah 38b": ("bavli", "Avodah Zarah"),
    "Jeremiah 44": ("neviim", "Jeremiah"),
    "Jeremiah 47": ("neviim", "Jeremiah"),
    "Psalms 16": ("ketuvim", "Psalms"),
    # Tracked one perek a day, so the unit is the perek, not perek:mishnah.
    "Mishnah Shabbat 1": ("mishnah", "Mishnah Shabbat"),
    "Shulchan Arukh, Orach Chayim 1": ("shulchan_aruch", "Shulchan Arukh, Orach Chayim"),
    "Orchot Tzadikim 11": ("mussar", "Orchot Tzadikim"),
    "Mesillat Yesharim 1": ("mussar", "Mesillat Yesharim"),
    "Likutei Moharan 1:1": ("chassidus", "Likutei Moharan"),
    "Bereshit Rabbah 3:5": ("midrash", "Bereshit Rabbah"),
    "Sha'arei Teshuvah 1:29": ("mussar", "Sha'arei Teshuvah"),
    "Mishneh Torah, Foreign Worship and Customs of the Nations 5:2": (
        "mishneh_torah",
        "Mishneh Torah, Foreign Worship and Customs of the Nations",
    ),
    "Mishneh Torah, Human Dispositions 5:8": ("mishneh_torah", "Mishneh Torah, Human Dispositions"),
    "Berakhot 13a": ("bavli", "Berakhot"),
}

ALLOWED_SEPARATORS = set(" ,;:.-–—()[]/'\"0123456789")
"""Includes the semicolon: Tanya's Sefaria titles carry a literal one, e.g.
``תניא, חלק ראשון; ליקוטי אמרים``."""


@pytest.fixture(scope="session")
async def seeded(db_engine: object) -> AsyncIterator[AsyncSession]:
    """Crawl the real API and seed a real Postgres, once for the whole module."""
    from sidra.db.engine import create_session_factory

    async with httpx.AsyncClient(timeout=180.0) as async_http:
        client = SefariaClient(async_http, SEFARIA_BASE_URL)
        with httpx.Client(timeout=300.0) as sync_http:
            result = await crawl_catalog(client, sync_http, include_links=True)

    factory = create_session_factory(db_engine)  # type: ignore[arg-type]
    async with factory() as session:
        await seed_from_snapshot(session, result.payload)
        await session.commit()
        yield session
        from sidra.db.seed import clear_catalog

        await clear_catalog(session)
        await session.commit()


async def _work(session: AsyncSession, ref_title: str) -> Work:
    return (await session.execute(select(Work).where(Work.ref_title == ref_title))).scalar_one()


@pytest.mark.parametrize("ref", sorted(SEED_REFS))
async def test_every_seed_ref_resolves(seeded: AsyncSession, ref: str) -> None:
    corpus_id, ref_title = SEED_REFS[ref]
    work = await _work(seeded, ref_title)
    assert work.corpus_id == corpus_id
    resolved = {
        unit_at(work.ref_title, work.address_scheme, work.shape, seq).ref for seq in range(1, work.unit_count + 1)
    }
    assert ref in resolved, f"{ref} is not among {work.ref_title}'s {work.unit_count} units"


async def test_the_gemara_debt_is_twenty_amudim(seeded: AsyncSession) -> None:
    work = await _work(seeded, "Avodah Zarah")
    amudim = real_amudim(work.shape)
    actual, scheduled = amudim.index("28b") + 1, amudim.index("38b") + 1
    assert scheduled - actual == 20
    assert unit_at(work.ref_title, work.address_scheme, work.shape, actual).label_he == "כ״ח ע״ב"


async def test_the_neviim_debt_is_three_perakim(seeded: AsyncSession) -> None:
    work = await _work(seeded, "Jeremiah")
    assert unit_at(work.ref_title, work.address_scheme, work.shape, 47).ref == "Jeremiah 47"
    assert 47 - 44 == 3


async def test_mishnah_shabbat_one_one_is_corpus_ordinal_seventy_six(seeded: AsyncSession) -> None:
    rows = (
        (await seeded.execute(select(Work).where(Work.corpus_id == "mishnah").order_by(Work.corpus_seq)))
        .scalars()
        .all()
    )
    assert corpus_ordinal(rows, "Mishnah Shabbat", 1) == 76


async def test_tamid_starts_at_25b_and_nazir_omits_33b(seeded: AsyncSession) -> None:
    tamid = await _work(seeded, "Tamid")
    assert unit_at(tamid.ref_title, AddressScheme.DAF_AMUD, tamid.shape, 1).addr == ("25b",)
    nazir = await _work(seeded, "Nazir")
    assert "33b" not in real_amudim(nazir.shape)


async def test_every_other_masechta_starts_at_2a(seeded: AsyncSession) -> None:
    rows = (await seeded.execute(select(Work).where(Work.corpus_id == "bavli"))).scalars().all()
    starts = {work.ref_title: real_amudim(work.shape)[0] for work in rows}
    assert starts.pop("Tamid") == "25b"
    assert set(starts.values()) == {"2a"}


async def test_orchot_tzadikim_has_twenty_eight_named_gates(seeded: AsyncSession) -> None:
    work = await _work(seeded, "Orchot Tzadikim")
    assert work.unit_count == 28
    assert work.labels is not None and len(work.labels) == 28
    assert work.labels_he is not None and not any(label.endswith("\n") for label in work.labels_he)
    gate = unit_at(
        work.ref_title,
        work.address_scheme,
        work.shape,
        11,
        labels=work.labels,
        labels_he=work.labels_he,
    )
    assert "החרטה" in gate.label_he


async def test_the_catalog_matches_every_expected_count(seeded: AsyncSession) -> None:
    assert await check_catalog(seeded, load_expected_counts()) == []


async def test_the_ein_mishpat_map_is_complete(seeded: AsyncSession) -> None:
    """A silently truncated link ingest must fail the gate."""
    from sidra.db.models import TopicLink

    direct = await seeded.scalar(select(func.count()).select_from(TopicLink).where(TopicLink.kind == "ein_mishpat"))
    assert direct == 118805


async def test_inferred_edges_are_distinguishable_from_citations(seeded: AsyncSession) -> None:
    """Tur-bridge edges are inferences. Presenting one as a citation would misstate the source."""
    from sidra.db.models import TopicLink

    bridged = (await seeded.execute(select(TopicLink).where(TopicLink.kind == "tur_bridge").limit(5))).scalars().all()
    assert bridged
    assert all(row.confidence == "inferred" for row in bridged)
    assert all(row.to_ref.startswith("Shulchan Arukh, ") for row in bridged)

    direct = (await seeded.execute(select(TopicLink).where(TopicLink.kind == "ein_mishpat").limit(5))).scalars().all()
    assert all(row.confidence == "direct" for row in direct)


async def test_the_parsha_cycle_is_stored(seeded: AsyncSession) -> None:
    assert await seeded.scalar(select(func.count()).select_from(LearnableUnit)) == 432
    shlishi = (
        await seeded.execute(
            select(LearnableUnit).where(
                LearnableUnit.label_en == "Shlishi",
                LearnableUnit.resolved_ref == "Deuteronomy 26:16-26:19",
            )
        )
    ).scalar_one()
    assert shlishi.label_he == "שלישי"


async def test_amrams_own_spellings_resolve(seeded: AsyncSession) -> None:
    for alias, expected_prefix in (
        ("Mesechet Avoda Zara", "Avodah Zarah"),
        ("Brachot", "Berakhot"),
        ("Hilchos Daos", "Mishneh Torah, Human Dispositions"),
        ("Chovot Halevavot", "Duties of the Heart"),
    ):
        # Sefaria and the local file can both supply the same spelling, so several rows is normal.
        rows = (
            (
                await seeded.execute(
                    select(Work.ref_title)
                    .join(TitleAlias, TitleAlias.work_id == Work.id)
                    .where(TitleAlias.alias == alias)
                )
            )
            .scalars()
            .all()
        )
        assert rows, f"{alias} resolves to nothing"
        assert any(row.startswith(expected_prefix) for row in rows), f"{alias} resolved to {rows}"


async def test_the_hebrew_guard_passes_over_the_whole_catalog(seeded: AsyncSession) -> None:
    """Only Hebrew and known separators, and the check must not pass vacuously."""

    def clean(text: str) -> bool:
        return all(c in ALLOWED_SEPARATORS or HEBREW_BLOCK_START <= c <= HEBREW_BLOCK_END for c in text)

    works = (await seeded.execute(select(Work.ref_title, Work.title_he))).all()
    assert works
    hebrew_seen = False
    for ref_title, title_he in works:
        assert clean(title_he), f"{ref_title}: {title_he!r} carries a non-Hebrew character"
        hebrew_seen = hebrew_seen or any(HEBREW_BLOCK_START <= c <= HEBREW_BLOCK_END for c in title_he)
    assert hebrew_seen, "no work carries Hebrew; the guard would pass vacuously"

    units = (await seeded.execute(select(LearnableUnit.label_en, LearnableUnit.label_he))).all()
    for label_en, label_he in units:
        assert clean(label_he), f"{label_en}: {label_he!r} carries a non-Hebrew character"
