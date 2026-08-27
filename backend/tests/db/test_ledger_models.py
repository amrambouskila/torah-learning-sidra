from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.db.models import Advance, Chavrusa, Tag, Track, TrackAlignment, track_tag
from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.track_kind import TrackKind

pytestmark = pytest.mark.integration

ANCHOR = date(2026, 8, 24)


async def _track(session: AsyncSession, name: str = "Gemara", **overrides: object) -> Track:
    defaults: dict[str, object] = {
        "name_en": name,
        "name_he": "גמרא",
        "category": Category.DAILY,
        "kind": TrackKind.CURATED_QUEUE,
        "corpus_id": None,
        "work_ref_title": "Avodah Zarah",
        "rate": 1,
        "period": Period.DAY,
        "anchor_date": ANCHOR,
        "anchor_ordinal": 74,
        "starts_on": None,
        "chavrusa_id": None,
        "is_active": True,
    }
    track = Track(**{**defaults, **overrides})  # type: ignore[arg-type]
    session.add(track)
    await session.flush()
    return track


async def test_a_track_round_trips(db_session: AsyncSession) -> None:
    track = await _track(db_session)
    found = (await db_session.execute(select(Track).where(Track.id == track.id))).scalar_one()
    assert found.category is Category.DAILY
    assert found.kind is TrackKind.CURATED_QUEUE
    assert found.period is Period.DAY
    assert found.anchor_date == ANCHOR
    assert found.name_he == "גמרא"
    assert found.starts_on is None


async def test_a_future_track_carries_its_start_date(db_session: AsyncSession) -> None:
    """The three parsha-weekly works begin at Shabbos Bereishis, 10 October 2026."""
    track = await _track(db_session, "Likutei Sichot", starts_on=date(2026, 10, 10), period=Period.WEEK)
    found = (await db_session.execute(select(Track).where(Track.id == track.id))).scalar_one()
    assert found.starts_on == date(2026, 10, 10)


async def test_track_names_are_unique(db_session: AsyncSession) -> None:
    await _track(db_session, "Neviim")
    with pytest.raises(IntegrityError):
        await _track(db_session, "Neviim")
    await db_session.rollback()


async def test_a_chavrusa_track_names_its_partner(db_session: AsyncSession) -> None:
    chavrusa = Chavrusa(name="Yosef Mendelson & David Gofman", notes="Bereishit Rabbah")
    db_session.add(chavrusa)
    await db_session.flush()
    track = await _track(
        db_session, "Bereishit Rabbah", category=Category.CHAVRUSA, period=Period.NONE, chavrusa_id=chavrusa.id
    )
    found = (await db_session.execute(select(Track).where(Track.id == track.id))).scalar_one()
    assert found.chavrusa_id == chavrusa.id
    assert found.period is Period.NONE


async def test_an_advance_round_trips_with_a_hebrew_note(db_session: AsyncSession) -> None:
    track = await _track(db_session)
    db_session.add(
        Advance(
            track_id=track.id,
            from_ordinal=53,
            to_ordinal=54,
            unit_count=1,
            occurred_at=datetime.now(UTC),
            hebrew_date="י״א אלול תשפ״ו",
            note="שאלה לרבי יעקב",
        )
    )
    await db_session.flush()
    found = (await db_session.execute(select(Advance).where(Advance.track_id == track.id))).scalar_one()
    assert found.occurred_at.tzinfo is not None
    assert found.hebrew_date == "י״א אלול תשפ״ו"
    assert found.note == "שאלה לרבי יעקב"


async def test_an_advance_may_carry_no_note(db_session: AsyncSession) -> None:
    track = await _track(db_session)
    db_session.add(
        Advance(
            track_id=track.id,
            from_ordinal=53,
            to_ordinal=54,
            unit_count=1,
            occurred_at=datetime.now(UTC),
            hebrew_date="י״א אלול תשפ״ו",
        )
    )
    await db_session.flush()
    assert (await db_session.execute(select(Advance))).scalar_one().note is None


async def test_tag_names_are_unique(db_session: AsyncSession) -> None:
    db_session.add(Tag(name="parsha", name_he="פרשה", color="#1f4e79"))
    await db_session.flush()
    db_session.add(Tag(name="parsha"))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_a_tag_spans_categories(db_session: AsyncSession) -> None:
    """The whole point of tags: `parsha` covers Chumash in DAILY and three works in SHABBAT."""
    tag = Tag(name="parsha", name_he="פרשה")
    db_session.add(tag)
    await db_session.flush()
    chumash = await _track(db_session, "Chumash", category=Category.DAILY, kind=TrackKind.PARSHA_ALIYAH)
    sichot = await _track(
        db_session, "Likutei Sichot", category=Category.SHABBAT, kind=TrackKind.PARSHA_WEEKLY, period=Period.WEEK
    )
    await db_session.execute(
        insert(track_tag), [{"track_id": chumash.id, "tag_id": tag.id}, {"track_id": sichot.id, "tag_id": tag.id}]
    )
    await db_session.flush()

    tagged = (
        (
            await db_session.execute(
                select(Track.category)
                .join(track_tag, track_tag.c.track_id == Track.id)
                .where(track_tag.c.tag_id == tag.id)
            )
        )
        .scalars()
        .all()
    )
    assert set(tagged) == {Category.DAILY, Category.SHABBAT}


async def test_deleting_a_tag_removes_the_association_not_the_track(db_session: AsyncSession) -> None:
    tag = Tag(name="parsha")
    db_session.add(tag)
    await db_session.flush()
    track = await _track(db_session, "Chumash")
    await db_session.execute(insert(track_tag), [{"track_id": track.id, "tag_id": tag.id}])
    await db_session.flush()

    await db_session.execute(delete(Tag).where(Tag.id == tag.id))
    await db_session.flush()

    assert (await db_session.execute(select(Track).where(Track.id == track.id))).scalar_one() is not None
    assert (await db_session.execute(select(track_tag))).first() is None


async def test_an_alignment_links_two_tracks(db_session: AsyncSession) -> None:
    """The Gemara track follows Rabbi Jacob's Mishneh Torah track."""
    gemara = await _track(db_session, "Gemara")
    rambam = await _track(db_session, "Rabbi Jacob", category=Category.CHAVRUSA, period=Period.NONE)
    db_session.add(TrackAlignment(follower_track_id=gemara.id, leader_track_id=rambam.id, mode="topic_map"))
    await db_session.flush()
    found = (await db_session.execute(select(TrackAlignment))).scalar_one()
    assert found.follower_track_id == gemara.id
    assert found.leader_track_id == rambam.id
    assert found.mode == "topic_map"


async def test_a_track_follows_at_most_one_leader(db_session: AsyncSession) -> None:
    gemara = await _track(db_session, "Gemara")
    first = await _track(db_session, "Rabbi Jacob", category=Category.CHAVRUSA, period=Period.NONE)
    second = await _track(db_session, "David Cohen", category=Category.CHAVRUSA, period=Period.NONE)
    db_session.add(TrackAlignment(follower_track_id=gemara.id, leader_track_id=first.id))
    await db_session.flush()
    db_session.add(TrackAlignment(follower_track_id=gemara.id, leader_track_id=second.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_ids_are_uuids(db_session: AsyncSession) -> None:
    track = await _track(db_session)
    assert isinstance(track.id, uuid.UUID)
