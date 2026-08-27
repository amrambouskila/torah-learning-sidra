from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.db.models import Advance, Snapshot, TopicLink, Track, Work
from sidra.db.seed import DIRECT_CONFIDENCE, EIN_MISHPAT_KIND
from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.track_kind import TrackKind
from sidra.sequence import masechta_map as map_module
from tests.api.conftest import AS_OF_DATE, HEBREW_AS_OF

pytestmark = pytest.mark.integration

# The Rambam's real order out of Hilchos Avoda Zara, reduced to the three books that make the
# rule visible: one about a masechta, one about none, one about a different masechta.
BOOKS = [
    ("Mishneh Torah, Foreign Worship", 12),
    ("Mishneh Torah, Repentance", 8),
    ("Mishneh Torah, Reading the Shema", 10),
    ("Mishneh Torah, The Order of Prayer", 3),
]
LINKS = [
    # Foreign Worship leads Avodah Zarah over Sanhedrin by more than half again.
    *[("Mishneh Torah, Foreign Worship 1:1", f"Avodah Zarah {n}a") for n in range(2, 12)],
    *[("Mishneh Torah, Foreign Worship 1:2", f"Sanhedrin {n}a") for n in range(2, 6)],
    # Repentance is split, exactly as it is in life: no masechta owns it.
    *[("Mishneh Torah, Repentance 1:1", f"Yoma {n}a") for n in range(2, 6)],
    *[("Mishneh Torah, Repentance 1:2", f"Sanhedrin {n}b") for n in range(2, 6)],
    # Kriyas Shema is overwhelmingly Berakhot.
    *[("Mishneh Torah, Reading the Shema 1:1", f"Berakhot {n}a") for n in range(2, 12)],
    # A Rambam ref this track does not run through: shares the prefix, owned by no work here.
    ("Mishneh Torah, Something Else 1:1", "Shabbat 2a"),
]


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """The masechta map is cached per snapshot; each test builds its own catalog."""
    map_module._CACHE.clear()  # noqa: SLF001 - the cache is this module's own


async def _rambam(session: AsyncSession, *, at_halachah: int = 5) -> Track:
    snapshot_id = (await session.execute(select(Snapshot).limit(1))).scalar_one().id
    for seq, (ref_title, halachos) in enumerate(BOOKS, start=1):
        session.add(
            Work(
                corpus_id="mishneh_torah",
                corpus_seq=seq,
                index_title=ref_title,
                ref_title=ref_title,
                title_he=f"he-{ref_title}",
                granularity=Granularity.HALAKHAH,
                address_scheme=AddressScheme.NESTED,
                shape=[halachos],
                labels=None,
                labels_he=None,
                unit_count=halachos,
                source="sefaria",
                snapshot_id=snapshot_id,
            )
        )
    for from_ref, to_ref in LINKS:
        session.add(
            TopicLink(
                from_ref=from_ref,
                to_ref=to_ref,
                from_category="Halakhah",
                to_category="Talmud",
                kind=EIN_MISHPAT_KIND,
                anchor_group=from_ref,
                confidence=DIRECT_CONFIDENCE,
                snapshot_id=snapshot_id,
            )
        )
    track = Track(
        name_en="Rabbi Jacob — Mishneh Torah",
        name_he="הרב יעקב",
        category=Category.CHAVRUSA,
        kind=TrackKind.CORPUS,
        corpus_id="mishneh_torah",
        work_ref_title=None,
        rate=1,
        period=Period.NONE,
        anchor_date=AS_OF_DATE,
        anchor_ordinal=1,
        is_active=True,
    )
    session.add(track)
    await session.flush()
    session.add(
        Advance(
            track_id=track.id,
            from_ordinal=at_halachah - 1,
            to_ordinal=at_halachah,
            unit_count=1,
            occurred_at=datetime.combine(AS_OF_DATE, datetime.min.time(), tzinfo=UTC),
            hebrew_date=HEBREW_AS_OF,
            note=None,
        )
    )
    await session.flush()
    return track


async def test_a_section_with_no_masechta_does_not_move_him(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    """Amram's rule end to end: the Rambam goes Avoda Zara then Teshuvah, Teshuvah has no masechta
    of its own, so the stage he is in covers both and the Gemara stays where it is."""
    track = await _rambam(seeded_session)
    body = (await client.get(f"/api/sequence/{track.id}")).json()

    first = body["stages"][0]
    assert first["masechta_en"] == "Avodah Zarah"
    assert first["is_current"] is True
    assert [work["ref_title"] for work in first["works"]] == [
        "Mishneh Torah, Foreign Worship",
        "Mishneh Torah, Repentance",
    ]


async def test_the_next_masechta_and_how_far_off_it_is(client: httpx.AsyncClient, seeded_session: AsyncSession) -> None:
    """The number he actually wants: how much Rambam is left before the Gemara has to move."""
    track = await _rambam(seeded_session, at_halachah=5)
    body = (await client.get(f"/api/sequence/{track.id}")).json()

    nxt = body["stages"][1]
    assert nxt["masechta_en"] == "Berakhot"
    assert nxt["is_current"] is False
    # Seven left of Foreign Worship's twelve, then all eight of Repentance.
    assert nxt["halachos_until"] == 7 + 8
    # Kriyas Shema's ten, plus Seder Tefillos' three riding along behind it with no masechta.
    assert nxt["halachos_in_stage"] == 10 + 3


async def test_the_stage_he_is_in_is_zero_away(client: httpx.AsyncClient, seeded_session: AsyncSession) -> None:
    track = await _rambam(seeded_session)
    body = (await client.get(f"/api/sequence/{track.id}")).json()
    assert body["stages"][0]["halachos_until"] == 0


async def test_each_pairing_carries_the_evidence_behind_it(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    """A close call must stay visible rather than being presented as a fact."""
    track = await _rambam(seeded_session)
    first = (await client.get(f"/api/sequence/{track.id}")).json()["stages"][0]
    assert first["links"] == 10
    assert first["runner_up"] == "Sanhedrin"
    assert 0 < first["share"] <= 1


async def test_the_hebrew_comes_from_the_catalog(client: httpx.AsyncClient, seeded_session: AsyncSession) -> None:
    """Never assembled here. Berakhot's Hebrew is the catalog's own."""
    track = await _rambam(seeded_session)
    body = (await client.get(f"/api/sequence/{track.id}")).json()
    assert body["stages"][1]["masechta_he"] == "ברכות"


async def test_standing_inside_a_section_with_no_masechta_adopts_the_one_ahead(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    """Inside Teshuvah, the stage he is in is the one Kriyas Shema is about to name."""
    track = await _rambam(seeded_session, at_halachah=14)
    body = (await client.get(f"/api/sequence/{track.id}")).json()
    assert body["stages"][0]["masechta_en"] == "Berakhot"


async def test_a_track_that_is_not_a_code_is_refused(client: httpx.AsyncClient) -> None:
    """A Gemara or Chumash track has no Ein Mishpat to sequence."""
    rows = (await client.get("/api/tracks")).json()
    neviim = next(row for row in rows if row["name_en"] == "Neviim")
    response = await client.get(f"/api/sequence/{neviim['id']}")
    assert response.status_code == 422
    assert "not a code track" in response.json()["detail"]


async def test_an_unknown_track_is_a_404(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"/api/sequence/{uuid.uuid4()}")).status_code == 404


async def test_the_number_of_stages_can_be_capped(client: httpx.AsyncClient, seeded_session: AsyncSession) -> None:
    track = await _rambam(seeded_session)
    body = (await client.get(f"/api/sequence/{track.id}", params={"limit": 1})).json()
    assert len(body["stages"]) == 1


async def test_a_code_track_never_opened_starts_at_its_beginning(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    track = await _rambam(seeded_session, at_halachah=0)
    body = (await client.get(f"/api/sequence/{track.id}")).json()
    assert body["at"] is None
    assert body["stages"][0]["masechta_en"] == "Avodah Zarah"


async def test_a_position_past_the_end_of_the_code_has_nothing_ahead(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    """A seatbelt, in the same spirit as effective_anchor: this codebase never writes such a row,
    but one can arrive from an older ledger export. It reports nothing ahead rather than raising
    across the whole screen."""
    track = await _rambam(seeded_session, at_halachah=99)
    body = (await client.get(f"/api/sequence/{track.id}")).json()
    assert body["at"] is None
    assert body["stages"] == []


async def test_a_closing_run_with_no_masechta_is_shown_as_one(
    client: httpx.AsyncClient, seeded_session: AsyncSession
) -> None:
    """Hilchos Seder Tefillos cites no Gemara at all, and it is the last thing here. A run that
    never finds a masechta is named as such rather than silently attached to the one before."""
    track = await _rambam(seeded_session, at_halachah=31)
    body = (await client.get(f"/api/sequence/{track.id}")).json()
    assert [stage["masechta_en"] for stage in body["stages"]] == [None]
    assert body["stages"][0]["share"] is None


async def test_the_map_is_computed_once_and_reused(client: httpx.AsyncClient, seeded_session: AsyncSession) -> None:
    """It is a property of the catalog, not of the ledger, so a second call must not rebuild it."""
    track = await _rambam(seeded_session)
    first = (await client.get(f"/api/sequence/{track.id}")).json()
    assert len(map_module._CACHE) == 1  # noqa: SLF001 - the cache is this module's own
    second = (await client.get(f"/api/sequence/{track.id}")).json()
    assert second == first
