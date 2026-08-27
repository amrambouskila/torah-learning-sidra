"""Verification against the real Sefaria API.

Marked ``live`` and excluded from CI. These tests exist because a fixture can encode the same wrong
belief as the code that reads it — only the real API contradicts it. An earlier draft of this plan
carried Tamid's first shape index as 51, taken from a research report; it is 49, and index 51 is
26b. Every fixture-based test agreed with the error.

Run deliberately:  uv run pytest -m live
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.bavli_amudim import real_amudim
from sidra.catalog.resolve import unit_at, unit_count
from sidra.catalog.sefaria_client import SefariaClient
from sidra.catalog.shape import parse_shape
from sidra.constants import SEFARIA_BASE_URL

pytestmark = pytest.mark.live

SEDER_PREFIX = "Seder "


@pytest.fixture(scope="session")
async def sefaria() -> AsyncIterator[SefariaClient]:
    async with httpx.AsyncClient(timeout=90.0) as client:
        yield SefariaClient(client, SEFARIA_BASE_URL)


async def test_bavli_holds_thirty_seven_masechtos_and_5349_real_amudim(sefaria: SefariaClient) -> None:
    nodes = [node for node in parse_shape(await sefaria.shape("Talmud/Bavli")) if node.section.startswith(SEDER_PREFIX)]
    assert len(nodes) == 37
    assert sum(unit_count(AddressScheme.DAF_AMUD, node.chapters) for node in nodes) == 5349


async def test_tamid_starts_at_25b(sefaria: SefariaClient) -> None:
    """The trap: first non-empty index is 49, not 51. Index 51 would be 26b."""
    node = parse_shape(await sefaria.shape("Tamid"))[0]
    assert next(index for index, count in enumerate(node.chapters) if count) == 49
    amudim = real_amudim(node.chapters)
    assert amudim[0] == "25b"
    assert amudim[-1] == "33b"
    assert len(amudim) == 17


async def test_nazir_has_a_mid_masechta_gap(sefaria: SefariaClient) -> None:
    """Nazir runs 2a..66b but index 65 (33b) carries no text."""
    node = parse_shape(await sefaria.shape("Nazir"))[0]
    assert [index for index, count in enumerate(node.chapters) if count == 0] == [0, 1, 65]
    amudim = real_amudim(node.chapters)
    assert "33b" not in amudim
    assert len(amudim) == 129
    assert amudim[-1] == "66b"


async def test_the_naive_bavli_formula_really_is_wrong(sefaria: SefariaClient) -> None:
    """slots minus leading zeros gives 5,350; counting non-empty slots gives the true 5,349."""
    nodes = [node for node in parse_shape(await sefaria.shape("Talmud/Bavli")) if node.section.startswith(SEDER_PREFIX)]
    slots = sum(node.length for node in nodes)
    leading = sum(next((i for i, count in enumerate(node.chapters) if count), 0) for node in nodes)
    assert slots == 5471
    assert slots - leading == 5350
    assert sum(unit_count(AddressScheme.DAF_AMUD, node.chapters) for node in nodes) == 5349


async def test_avodah_zarah_resolves_the_real_gemara_position(sefaria: SefariaClient) -> None:
    node = parse_shape(await sefaria.shape("Avodah Zarah"))[0]
    assert node.length == 152
    amudim = real_amudim(node.chapters)
    assert len(amudim) == 150

    actual = amudim.index("28b") + 1
    scheduled = amudim.index("38b") + 1
    assert scheduled - actual == 20
    assert unit_at("Avodah Zarah", AddressScheme.DAF_AMUD, node.chapters, actual).ref == "Avodah Zarah 28b"
    assert unit_at("Avodah Zarah", AddressScheme.DAF_AMUD, node.chapters, actual).label_he == "כ״ח ע״ב"


async def test_human_dispositions_resolves_the_real_rambam_position(sefaria: SefariaClient) -> None:
    node = parse_shape(await sefaria.shape("Mishneh Torah, Human Dispositions"))[0]
    assert node.length == 7
    assert unit_count(AddressScheme.NESTED, node.chapters) == 71

    seq = sum(node.chapters[:4]) + 8
    unit = unit_at("Mishneh Torah, Human Dispositions", AddressScheme.NESTED, node.chapters, seq)
    assert unit.addr == ("5", "8")
    assert unit.ref == "Mishneh Torah, Human Dispositions 5:8"


async def test_jeremiah_resolves_the_real_neviim_position(sefaria: SefariaClient) -> None:
    node = parse_shape(await sefaria.shape("Jeremiah"))[0]
    assert node.length == 52
    assert unit_at("Jeremiah", AddressScheme.FLAT, node.chapters, 47).ref == "Jeremiah 47"
    assert unit_at("Jeremiah", AddressScheme.FLAT, node.chapters, 44).label_he == "מ״ד"


async def test_a_two_hundred_with_an_error_body_really_happens(sefaria: SefariaClient) -> None:
    """The behaviour the client exists for, confirmed against the real API."""
    from sidra.catalog.sefaria_error import SefariaError

    with pytest.raises(SefariaError):
        await sefaria.index("Nonesuch Book Of Nothing")
