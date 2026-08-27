"""Tag CRUD.

Tags are pure labels that cut across the three fixed categories -- no cadence, no rules, no side
effects. Deleting one removes the association and never the track.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.api.deps import get_session
from sidra.api.models.tag_read import TagRead
from sidra.api.models.tag_write import TagCreate, TagUpdate
from sidra.db.models import Tag, track_tag

router = APIRouter(prefix="/api/tags", tags=["tags"])


async def _counts(session: AsyncSession) -> dict[uuid.UUID, int]:
    rows = await session.execute(select(track_tag.c.tag_id, func.count()).group_by(track_tag.c.tag_id))
    return {tag_id: count for tag_id, count in rows.all()}


async def _tag_or_404(session: AsyncSession, tag_id: uuid.UUID) -> Tag:
    tag = (await session.execute(select(Tag).where(Tag.id == tag_id))).scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=404, detail=f"no tag with id {tag_id}")
    return tag


@router.get("", response_model=list[TagRead])
async def list_tags(session: AsyncSession = Depends(get_session)) -> list[TagRead]:
    tags = (await session.execute(select(Tag).order_by(Tag.name))).scalars().all()
    counts = await _counts(session)
    return [TagRead.of(tag, counts.get(tag.id, 0)) for tag in tags]


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
async def create_tag(body: TagCreate, session: AsyncSession = Depends(get_session)) -> TagRead:
    tag = Tag(name=body.name, name_he=body.name_he, color=body.color)
    session.add(tag)
    try:
        await session.flush()
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail=f"a tag named {body.name!r} already exists") from error
    return TagRead.of(tag, 0)


@router.patch("/{tag_id}", response_model=TagRead)
async def update_tag(tag_id: uuid.UUID, body: TagUpdate, session: AsyncSession = Depends(get_session)) -> TagRead:
    """Every field is optional; an omitted field is left alone rather than cleared."""
    tag = await _tag_or_404(session, tag_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tag, field, value)
    try:
        await session.flush()
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail=f"a tag named {body.name!r} already exists") from error
    return TagRead.of(tag, (await _counts(session)).get(tag.id, 0))


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Response:
    """Removes the label and its associations. The tracks that wore it are untouched."""
    await _tag_or_404(session, tag_id)
    await session.execute(delete(track_tag).where(track_tag.c.tag_id == tag_id))
    await session.execute(delete(Tag).where(Tag.id == tag_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
