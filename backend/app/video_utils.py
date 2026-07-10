"""视频序列化与每日限额辅助。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import DAILY_UPLOAD_LIMIT
from .models import FeaturedSubmission, FeaturedVideo, JumpVideo
from .time_utils import today_cn_str


def parse_score_detail(raw: str) -> dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def serialize_video(video: JumpVideo, *, include_private: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": video.id,
        "username": video.username,
        "title": video.title or "",
        "description": video.description or "",
        "video_url": video.video_url or "",
        "cover_url": video.cover_url or "",
        "media_status": video.media_status,
        "media_error": video.media_error if include_private else "",
        "score_status": video.score_status,
        "score_error": video.score_error if include_private else "",
        "duration_sec": video.duration_sec,
        "jump_count": video.jump_count,
        "speed_per_min": video.speed_per_min,
        "fancy_count": video.fancy_count,
        "fancy_duration_sec": video.fancy_duration_sec,
        "ai_score": video.ai_score,
        "ai_score_detail": parse_score_detail(video.ai_score_detail),
        "is_public": video.is_public,
        "is_approved": video.is_approved,
        "published_at": video.published_at.isoformat() if video.published_at else None,
        "upload_date": video.upload_date,
        "created_at": video.created_at.isoformat() if video.created_at else None,
    }
    return data


async def user_uploaded_today(db: AsyncSession, username: str) -> JumpVideo | None:
    today = today_cn_str()
    r = await db.execute(
        select(JumpVideo)
        .where(JumpVideo.username == username, JumpVideo.upload_date == today)
        .order_by(JumpVideo.id.desc())
        .limit(1)
    )
    return r.scalar_one_or_none()


async def can_upload_today(db: AsyncSession, username: str) -> tuple[bool, JumpVideo | None]:
    existing = await user_uploaded_today(db, username)
    if existing and DAILY_UPLOAD_LIMIT <= 1:
        return False, existing
    if existing:
        r = await db.execute(
            select(func.count())
            .select_from(JumpVideo)
            .where(JumpVideo.username == username, JumpVideo.upload_date == today_cn_str())
        )
        count = int(r.scalar() or 0)
        if count >= DAILY_UPLOAD_LIMIT:
            return False, existing
    return True, existing


async def is_featured(db: AsyncSession, video_id: int) -> bool:
    r = await db.execute(select(FeaturedVideo.id).where(FeaturedVideo.video_id == video_id).limit(1))
    return r.scalar() is not None


async def pending_featured_submission(db: AsyncSession, video_id: int) -> FeaturedSubmission | None:
    r = await db.execute(
        select(FeaturedSubmission)
        .where(
            FeaturedSubmission.video_id == video_id,
            FeaturedSubmission.status == "pending",
        )
        .order_by(FeaturedSubmission.id.desc())
        .limit(1)
    )
    return r.scalar_one_or_none()
