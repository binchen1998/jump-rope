"""管理后台 API。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import check_admin_credentials, check_admin_password, create_admin_token, require_admin
from ..competition_utils import count_votes, serialize_competition, settle_competition
from ..db import get_db
from ..models import (
    CompetitionEntry,
    CompetitionReport,
    FeaturedSubmission,
    FeaturedVideo,
    JumpCompetition,
    JumpVideo,
)
from ..video_utils import serialize_video

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminLoginIn(BaseModel):
    username: str = "admin"
    password: str


class CompetitionIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    start_date: date
    submission_deadline: date
    end_date: date
    is_published: bool = True


class CompetitionUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    submission_deadline: Optional[date] = None
    end_date: Optional[date] = None
    is_published: Optional[bool] = None


class RemoveEntryIn(BaseModel):
    reason: str = ""


class FeaturedReviewIn(BaseModel):
    status: str
    reject_reason: str = ""


class FeaturedAddIn(BaseModel):
    video_id: int


class VideoModerationIn(BaseModel):
    is_approved: Optional[bool] = None
    is_public: Optional[bool] = None


@router.post("/login")
async def login(payload: AdminLoginIn):
    username = (payload.username or "admin").strip() or "admin"
    if not check_admin_credentials(username, payload.password) and not (
        username == "admin" and check_admin_password(payload.password)
    ):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"token": create_admin_token(), "username": username}


@router.get("/competitions")
async def admin_list_competitions(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    result = await db.execute(select(JumpCompetition).order_by(JumpCompetition.id.desc()))
    return {"items": [serialize_competition(c) for c in result.scalars().all()]}


@router.post("/competitions")
async def admin_create_competition(
    payload: CompetitionIn,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    if payload.submission_deadline < payload.start_date:
        raise HTTPException(status_code=400, detail="投稿截止不能早于开始日期")
    if payload.end_date < payload.submission_deadline:
        raise HTTPException(status_code=400, detail="结束日期不能早于投稿截止")

    comp = JumpCompetition(
        title=payload.title.strip(),
        description=payload.description or "",
        start_date=payload.start_date,
        submission_deadline=payload.submission_deadline,
        end_date=payload.end_date,
        is_published=payload.is_published,
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return serialize_competition(comp)


@router.put("/competitions/{competition_id}")
async def admin_update_competition(
    competition_id: int,
    payload: CompetitionUpdateIn,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    comp = await db.get(JumpCompetition, competition_id)
    if not comp:
        raise HTTPException(status_code=404, detail="比赛不存在")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(comp, k, v)
    start = comp.start_date
    deadline = comp.submission_deadline
    end = comp.end_date
    if deadline < start or end < deadline:
        raise HTTPException(status_code=400, detail="日期不合法")
    await db.commit()
    await db.refresh(comp)
    return serialize_competition(comp)


@router.get("/competitions/{competition_id}/entries")
async def admin_list_entries(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    result = await db.execute(
        select(CompetitionEntry, JumpVideo)
        .join(JumpVideo, JumpVideo.id == CompetitionEntry.video_id)
        .where(CompetitionEntry.competition_id == competition_id)
        .order_by(CompetitionEntry.id.desc())
    )
    items = []
    for entry, video in result.all():
        votes = entry.final_votes if entry.final_rank is not None else await count_votes(db, entry.id)
        items.append(
            {
                "id": entry.id,
                "competition_id": entry.competition_id,
                "video_id": entry.video_id,
                "username": entry.username,
                "status": entry.status,
                "removal_reason": entry.removal_reason,
                "submitted_at": entry.submitted_at.isoformat() if entry.submitted_at else None,
                "votes": votes,
                "final_rank": entry.final_rank,
                "video": serialize_video(video, include_private=True),
            }
        )
    return {"items": items}


@router.put("/competitions/entries/{entry_id}/remove")
async def admin_remove_entry(
    entry_id: int,
    payload: RemoveEntryIn,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    entry = await db.get(CompetitionEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="参赛作品不存在")
    entry.status = "removed"
    entry.removal_reason = payload.reason or ""
    entry.removed_at = datetime.utcnow()
    await db.commit()
    return {"ok": True}


@router.delete("/competitions/entries/{entry_id}")
async def admin_delete_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    entry = await db.get(CompetitionEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="参赛作品不存在")
    if entry.status != "removed":
        raise HTTPException(status_code=400, detail="只能删除已移出的作品")
    await db.delete(entry)
    await db.commit()
    return {"ok": True}


@router.post("/competitions/{competition_id}/settle")
async def admin_settle(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    comp = await db.get(JumpCompetition, competition_id)
    if not comp:
        raise HTTPException(status_code=404, detail="比赛不存在")
    ok = await settle_competition(db, comp)
    if not ok:
        raise HTTPException(status_code=400, detail="比赛已结算或不存在")
    await db.refresh(comp)
    return serialize_competition(comp)


@router.get("/competitions/{competition_id}/reports")
async def admin_list_reports(
    competition_id: int,
    status: str = Query("pending"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    result = await db.execute(
        select(CompetitionReport)
        .where(
            CompetitionReport.competition_id == competition_id,
            CompetitionReport.status == status,
        )
        .order_by(CompetitionReport.id.desc())
    )
    items = [
        {
            "id": r.id,
            "entry_id": r.entry_id,
            "username": r.username,
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in result.scalars().all()
    ]
    return {"items": items}


@router.put("/competitions/reports/{report_id}")
async def admin_update_report(
    report_id: int,
    status: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    report = await db.get(CompetitionReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="举报不存在")
    if status not in ("pending", "deleted"):
        raise HTTPException(status_code=400, detail="非法状态")
    report.status = status
    await db.commit()
    return {"ok": True}


@router.get("/videos")
async def admin_list_videos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    q: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    stmt = select(JumpVideo).order_by(JumpVideo.id.desc())
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where((JumpVideo.title.like(like)) | (JumpVideo.username.like(like)))
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    return {"items": [serialize_video(v, include_private=True) for v in result.scalars().all()]}


@router.put("/videos/{video_id}")
async def admin_moderate_video(
    video_id: int,
    payload: VideoModerationIn,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    video = await db.get(JumpVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if payload.is_approved is not None:
        video.is_approved = payload.is_approved
    if payload.is_public is not None:
        video.is_public = payload.is_public
    await db.commit()
    await db.refresh(video)
    return serialize_video(video, include_private=True)


@router.get("/featured-submissions")
async def admin_featured_submissions(
    status: str = Query("pending"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    result = await db.execute(
        select(FeaturedSubmission, JumpVideo)
        .join(JumpVideo, JumpVideo.id == FeaturedSubmission.video_id)
        .where(FeaturedSubmission.status == status)
        .order_by(FeaturedSubmission.id.desc())
    )
    items = []
    for sub, video in result.all():
        items.append(
            {
                "id": sub.id,
                "video_id": sub.video_id,
                "username": sub.username,
                "status": sub.status,
                "reject_reason": sub.reject_reason,
                "created_at": sub.created_at.isoformat() if sub.created_at else None,
                "reviewed_at": sub.reviewed_at.isoformat() if sub.reviewed_at else None,
                "video": serialize_video(video, include_private=True),
            }
        )
    return {"items": items}


@router.put("/featured-submissions/{submission_id}/review")
async def admin_review_featured(
    submission_id: int,
    payload: FeaturedReviewIn,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    sub = await db.get(FeaturedSubmission, submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="投稿不存在")
    if sub.status != "pending":
        raise HTTPException(status_code=400, detail="该投稿已审核")
    if payload.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status 须为 approved 或 rejected")

    sub.status = payload.status
    sub.reject_reason = payload.reject_reason if payload.status == "rejected" else ""
    sub.reviewed_at = datetime.utcnow()

    if payload.status == "approved":
        existing = (
            await db.execute(select(FeaturedVideo).where(FeaturedVideo.video_id == sub.video_id))
        ).scalar_one_or_none()
        if not existing:
            db.add(FeaturedVideo(video_id=sub.video_id, source="submission", sort_order=0))

    await db.commit()
    return {"ok": True, "status": sub.status}


@router.get("/featured")
async def admin_list_featured(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    result = await db.execute(
        select(FeaturedVideo, JumpVideo)
        .join(JumpVideo, JumpVideo.id == FeaturedVideo.video_id)
        .order_by(FeaturedVideo.sort_order.asc(), FeaturedVideo.id.desc())
    )
    items = []
    for feat, video in result.all():
        data = serialize_video(video, include_private=True)
        data["featured_id"] = feat.id
        data["featured_source"] = feat.source
        items.append(data)
    return {"items": items}


@router.post("/featured")
async def admin_add_featured(
    payload: FeaturedAddIn,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    video = await db.get(JumpVideo, payload.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    existing = (
        await db.execute(select(FeaturedVideo).where(FeaturedVideo.video_id == video.id))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="已在编辑推荐中")
    row = FeaturedVideo(video_id=video.id, source="admin", sort_order=0)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"ok": True, "featured_id": row.id}


@router.delete("/featured/{featured_id}")
async def admin_remove_featured(
    featured_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
):
    row = await db.get(FeaturedVideo, featured_id)
    if not row:
        raise HTTPException(status_code=404, detail="不存在")
    await db.delete(row)
    await db.commit()
    return {"ok": True}
