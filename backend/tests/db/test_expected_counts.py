from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.db.seed import seed_from_snapshot
from sidra.expected_counts import EXPECTED_COUNTS_PATH, check_catalog, load_expected_counts
from tests.db.test_seed import PAYLOAD

pytestmark = pytest.mark.integration

MATCHING = {
    "works": {"bavli": 1, "torah": 1},
    "units": {"bavli": 150, "torah": 2},
    "stored_units": 2,
    "topic_links": 3,
    "total_derivable_units": 152,
}


async def test_a_matching_catalog_reports_no_failures(db_session: AsyncSession) -> None:
    await seed_from_snapshot(db_session, PAYLOAD)
    assert await check_catalog(db_session, MATCHING) == []


@pytest.mark.parametrize(
    ("key", "path", "wrong", "fragment"),
    [
        ("works", "bavli", 99, "works[bavli]"),
        ("units", "bavli", 5349, "units[bavli]"),
    ],
)
async def test_a_wrong_per_corpus_count_is_named(
    db_session: AsyncSession, key: str, path: str, wrong: int, fragment: str
) -> None:
    await seed_from_snapshot(db_session, PAYLOAD)
    expected = {**MATCHING, key: {**MATCHING[key], path: wrong}}  # type: ignore[dict-item]
    failures = await check_catalog(db_session, expected)
    assert any(fragment in failure for failure in failures)


async def test_a_missing_corpus_is_reported_rather_than_ignored(db_session: AsyncSession) -> None:
    """An absent corpus must fail loudly; a silently partial catalog is worse than an error."""
    await seed_from_snapshot(db_session, PAYLOAD)
    expected = {**MATCHING, "works": {**MATCHING["works"], "mishnah": 63}}
    failures = await check_catalog(db_session, expected)
    assert any("works[mishnah]" in failure and "found None" in failure for failure in failures)


@pytest.mark.parametrize(
    ("key", "fragment"),
    [
        ("stored_units", "stored_units"),
        ("topic_links", "topic_links"),
        ("total_derivable_units", "total_derivable_units"),
    ],
)
async def test_a_wrong_total_is_named(db_session: AsyncSession, key: str, fragment: str) -> None:
    await seed_from_snapshot(db_session, PAYLOAD)
    failures = await check_catalog(db_session, {**MATCHING, key: 999999})
    assert any(fragment in failure for failure in failures)


def test_the_expected_counts_file_exists_and_parses() -> None:
    assert EXPECTED_COUNTS_PATH.exists()
    counts = load_expected_counts()
    for key in ("works", "units", "stored_units", "topic_links", "total_derivable_units"):
        assert key in counts


def test_expected_counts_are_cached() -> None:
    assert load_expected_counts() is load_expected_counts()
