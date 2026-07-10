"""编辑推荐：投稿 / 列表 / 状态。"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import get_db
from ..models import FeaturedSubmission, FeaturedVideo, JumpVideo, User
from ..video_utils import is_featured, serialize_video

router = APIRouter(prefix="/api/featured", tags=["featured"])


class SubmissionIn(BaseModel):
    video_id: int = Field(..., ge=1)


@router.get("")
async def list_featured(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FeaturedVideo, JumpVideo)
        .join(JumpVideo, JumpVideo.id == FeaturedVideo.video_id)
        .where(JumpVideo.is_public.is_(True), JumpVideo.is_approved.is_(True))
        .order_by(FeaturedVideo.sort_order.asc(), FeaturedVideo.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for feat, video in result.all():
        data = serialize_video(video)
        data["featured_id"] = feat.id
        data["featured_source"] = feat.source
        items.append(data)
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/home")
async def featured_home(limit: int = Query(12, ge=1, le=30), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FeaturedVideo, JumpVideo)
        .join(JumpVideo, JumpVideo.id == FeaturedVideo.video_id)
        .where(JumpVideo.is_public.is_(True), JumpVideo.is_approved.is_(True))
        .order_by(FeaturedVideo.sort_order.asc(), FeaturedVideo.id.desc())
        .limit(limit)
    )
    items = []
    for feat, video in result.all():
        data = serialize_video(video)
        data["featured_id"] = feat.id
        items.append(data)
    return {"items": items}


@router.get("/status")
async def submission_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.utcnow() - timedelta(days=1)
    r = await db.execute(
        select(FeaturedSubmission)
        .where(
            FeaturedSubmission.username == user.username,
            FeaturedSubmission.created_at >= since,
        )
        .order_by(FeaturedSubmission.id.desc())
        .limit(1)
    )
    recent = r.scalar_one_or_none()
    return {
        "can_submit": recent is None,
        "recent_submission": (
            {
                "id": recent.id,
                "video_id": recent.video_id,
                "status": recent.status,
                "created_at": recent.created_at.isoformat() if recent.created_at else None,
            }
            if recent
            else None
        ),
    }


@router.get("/candidates")
async def submission_candidates(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(JumpVideo)
        .where(
            JumpVideo.username == user.username,
            JumpVideo.is_public.is_(True),
            JumpVideo.is_approved.is_(True),
            JumpVideo.score_status == "done",
        )
        .order_by(JumpVideo.id.desc())
        .limit(50)
    )
    items = []
    for video in result.scalars().all():
        data = serialize_video(video, include_private=True)
        data["already_featured"] = await is_featured(db, video.id)
        items.append(data)
    return {"items": items}


@router.post("/submissions")
async def create_submission(
    payload: SubmissionIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.utcnow() - timedelta(days=1)
    recent = (
        await db.execute(
            select(FeaturedSubmission)
            .where(
                FeaturedSubmission.username == user.username,
                FeaturedSubmission.created_at >= since,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if recent:
        raise HTTPException(status_code=400, detail="24 小时内只能投稿一次编辑推荐")

    video = await db.get(JumpVideo, payload.video_id)
    if not video or video.username != user.username:
        raise HTTPException(status_code=404, detail="视频不存在")
    if not video.is_public or video.score_status != "done":
        raise HTTPException(status_code=400, detail="请先发布已分析完成的视频")
    if await is_featured(db, video.id):
        raise HTTPException(status_code=400, detail="该视频已在编辑推荐中")

    pending = (
        await db.execute(
            select(FeaturedSubmission)
            .where(
                FeaturedSubmission.video_id == video.id,
                FeaturedSubmission.status == "pending",
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if pending:
        raise HTTPException(status_code=400, detail="该视频已有待审核投稿")

    row = FeaturedSubmission(video_id=video.id, username=user.username, status="pending")
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {
        "id": row.id,
        "video_id": row.video_id,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
