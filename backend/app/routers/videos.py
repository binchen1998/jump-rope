"""跳绳视频上传 / 我的作品 / 广场 / 轮询打分。"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user, get_optional_user
from ..config import MAX_UPLOAD_BYTES, MEDIA_DIR
from ..db import get_db
from ..models import JumpVideo, User
from ..scoring import probe_duration_sec
from ..time_utils import china_day_start_utc, today_cn_str
from ..video_utils import can_upload_today, serialize_video

router = APIRouter(prefix="/api/videos", tags=["videos"])


class PublishIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


@router.get("/stats")
async def site_stats(db: AsyncSession = Depends(get_db)):
    public_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(JumpVideo)
                .where(JumpVideo.is_public.is_(True), JumpVideo.is_approved.is_(True))
            )
        ).scalar()
        or 0
    )
    total_count = int((await db.execute(select(func.count()).select_from(JumpVideo))).scalar() or 0)
    today_start = china_day_start_utc()
    today_count = int(
        (
            await db.execute(
                select(func.count()).select_from(JumpVideo).where(JumpVideo.created_at >= today_start)
            )
        ).scalar()
        or 0
    )
    return {
        "public_count": public_count,
        "total_count": total_count,
        "today_count": today_count,
    }


@router.get("/upload-quota")
async def upload_quota(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ok, existing = await can_upload_today(db, user.username)
    return {
        "can_upload": ok,
        "upload_date": today_cn_str(),
        "today_video": serialize_video(existing, include_private=True) if existing else None,
    }


@router.get("/public")
async def public_plaza(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=50),
    sort: str = Query("latest"),
    q: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(JumpVideo).where(
        JumpVideo.is_public.is_(True),
        JumpVideo.is_approved.is_(True),
        JumpVideo.score_status == "done",
    )
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            (JumpVideo.title.like(like))
            | (JumpVideo.description.like(like))
            | (JumpVideo.username.like(like))
        )

    if sort == "jumps":
        stmt = stmt.order_by(func.coalesce(JumpVideo.jump_count, 0).desc(), JumpVideo.id.desc())
    elif sort == "score":
        stmt = stmt.order_by(func.coalesce(JumpVideo.ai_score, 0).desc(), JumpVideo.id.desc())
    elif sort == "speed":
        stmt = stmt.order_by(func.coalesce(JumpVideo.speed_per_min, 0).desc(), JumpVideo.id.desc())
    else:
        stmt = stmt.order_by(JumpVideo.id.desc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await db.execute(count_stmt)).scalar() or 0)

    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    items = [serialize_video(v) for v in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/mine")
async def my_videos(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count_r = await db.execute(
        select(func.count()).select_from(JumpVideo).where(JumpVideo.username == user.username)
    )
    total = int(count_r.scalar() or 0)
    result = await db.execute(
        select(JumpVideo)
        .where(JumpVideo.username == user.username)
        .order_by(JumpVideo.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [serialize_video(v, include_private=True) for v in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/upload")
async def upload_video(
    video: UploadFile = File(...),
    title: str = Form(""),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ok, existing = await can_upload_today(db, user.username)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail=f"每天只能上传 1 个视频，今日已上传 #{existing.id if existing else ''}",
        )

    raw = await video.read()
    if not raw:
        raise HTTPException(status_code=400, detail="空文件")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="视频过大（上限 200MB）")

    ext = Path(video.filename or "upload.webm").suffix.lower() or ".webm"
    if ext not in {".webm", ".mp4", ".mov", ".mkv", ".avi"}:
        ext = ".webm"

    staging = MEDIA_DIR / "staging" / f"{uuid.uuid4().hex}{ext}"
    staging.write_bytes(raw)

    # 尽量在入库前拦截超长视频（无 ffprobe 时跳过，交给 worker）
    duration = probe_duration_sec(staging)
    if duration > 120 + 1:
        staging.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="视频最长 2 分钟")

    row = JumpVideo(
        username=user.username,
        title=(title or "").strip()[:200] or f"{user.username} 的跳绳",
        description=(description or "").strip()[:2000],
        local_path=str(staging),
        media_status="pending",
        score_status="pending",
        upload_date=today_cn_str(),
        duration_sec=duration or None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return serialize_video(row, include_private=True)


@router.get("/{video_id}")
async def get_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    viewer: Optional[User] = Depends(get_optional_user),
):
    video = await db.get(JumpVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    is_owner = viewer and viewer.username == video.username
    if not video.is_public or not video.is_approved:
        if not is_owner:
            raise HTTPException(status_code=404, detail="视频不存在或未公开")
    return serialize_video(video, include_private=bool(is_owner))


@router.get("/{video_id}/score")
async def poll_score(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """前端每 10 秒轮询打分状态。"""
    video = await db.get(JumpVideo, video_id)
    if not video or video.username != user.username:
        raise HTTPException(status_code=404, detail="视频不存在")
    return serialize_video(video, include_private=True)


@router.post("/{video_id}/publish")
async def publish_video(
    video_id: int,
    payload: PublishIn | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = await db.get(JumpVideo, video_id)
    if not video or video.username != user.username:
        raise HTTPException(status_code=404, detail="视频不存在")
    if video.score_status != "done":
        raise HTTPException(status_code=400, detail="请等待 AI 分析完成后再发布")
    if not video.is_approved:
        raise HTTPException(status_code=400, detail="视频已被下架，无法发布")

    if payload:
        if payload.title is not None:
            video.title = payload.title.strip()[:200] or video.title
        if payload.description is not None:
            video.description = payload.description.strip()[:2000]

    video.is_public = True
    if not video.published_at:
        video.published_at = datetime.utcnow()
    await db.commit()
    await db.refresh(video)
    return serialize_video(video, include_private=True)


@router.post("/{video_id}/unpublish")
async def unpublish_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = await db.get(JumpVideo, video_id)
    if not video or video.username != user.username:
        raise HTTPException(status_code=404, detail="视频不存在")
    video.is_public = False
    await db.commit()
    await db.refresh(video)
    return serialize_video(video, include_private=True)


@router.delete("/{video_id}")
async def delete_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = await db.get(JumpVideo, video_id)
    if not video or video.username != user.username:
        raise HTTPException(status_code=404, detail="视频不存在")
    if video.is_public:
        raise HTTPException(status_code=400, detail="请先取消公开再删除")
    # 清理本地文件
    try:
        p = Path(video.local_path)
        if p.exists() and str(MEDIA_DIR) in str(p.resolve()):
            p.unlink(missing_ok=True)
    except OSError:
        pass
    await db.delete(video)
    await db.commit()
    return {"ok": True}
