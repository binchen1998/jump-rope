"""公开比赛 / 投稿 / 投票 API。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user, get_optional_user
from ..competition_utils import (
    count_votes,
    serialize_competition,
    submission_open,
    today_cn,
    voting_open,
)
from ..db import get_db
from ..models import CompetitionEntry, CompetitionReport, CompetitionVote, JumpCompetition, JumpVideo, User
from ..video_utils import serialize_video

router = APIRouter(prefix="/api/competitions", tags=["competitions"])


class SubmitIn(BaseModel):
    video_id: int = Field(..., ge=1)


class ReportIn(BaseModel):
    reason: str = Field(default="", max_length=500)


async def _entry_payload(
    db: AsyncSession,
    entry: CompetitionEntry,
    video: JumpVideo | None = None,
    *,
    viewer: Optional[User] = None,
) -> dict:
    if video is None:
        video = await db.get(JumpVideo, entry.video_id)
    votes = entry.final_votes if entry.final_rank is not None else await count_votes(db, entry.id)
    my_voted = False
    if viewer:
        r = await db.execute(
            select(CompetitionVote.id).where(
                CompetitionVote.entry_id == entry.id,
                CompetitionVote.username == viewer.username,
            )
        )
        my_voted = r.scalar() is not None
    payload = {
        "id": entry.id,
        "competition_id": entry.competition_id,
        "video_id": entry.video_id,
        "username": entry.username,
        "status": entry.status,
        "submitted_at": entry.submitted_at.isoformat() if entry.submitted_at else None,
        "votes": votes,
        "final_rank": entry.final_rank,
        "final_votes": entry.final_votes,
        "my_voted": my_voted,
        "video": serialize_video(video) if video else None,
    }
    return payload


@router.get("/current")
async def current_competition(db: AsyncSession = Depends(get_db)):
    today = today_cn()
    result = await db.execute(
        select(JumpCompetition)
        .where(JumpCompetition.is_published.is_(True))
        .order_by(JumpCompetition.start_date.desc())
    )
    comps = list(result.scalars().all())
    live = [c for c in comps if serialize_competition(c)["status"] == "live"]
    if live:
        return serialize_competition(live[0])
    upcoming = [c for c in comps if c.start_date >= today]
    if upcoming:
        upcoming.sort(key=lambda c: c.start_date)
        return serialize_competition(upcoming[0])
    if comps:
        return serialize_competition(comps[0])
    return None


@router.get("")
async def list_competitions(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JumpCompetition)
        .where(JumpCompetition.is_published.is_(True))
        .order_by(JumpCompetition.start_date.desc())
    )
    items = []
    for comp in result.scalars().all():
        data = serialize_competition(comp)
        if status and data["status"] != status:
            continue
        items.append(data)
    return {"items": items}


@router.get("/{competition_id}")
async def get_competition(competition_id: int, db: AsyncSession = Depends(get_db)):
    comp = await db.get(JumpCompetition, competition_id)
    if not comp or not comp.is_published:
        raise HTTPException(status_code=404, detail="比赛不存在")
    return serialize_competition(comp)


@router.get("/{competition_id}/entries")
async def list_entries(
    competition_id: int,
    sort: str = Query("votes"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    viewer: Optional[User] = Depends(get_optional_user),
):
    comp = await db.get(JumpCompetition, competition_id)
    if not comp or not comp.is_published:
        raise HTTPException(status_code=404, detail="比赛不存在")

    result = await db.execute(
        select(CompetitionEntry, JumpVideo)
        .join(JumpVideo, JumpVideo.id == CompetitionEntry.video_id)
        .where(
            CompetitionEntry.competition_id == competition_id,
            CompetitionEntry.status == "active",
        )
    )
    rows = list(result.all())
    payloads = [await _entry_payload(db, e, v, viewer=viewer) for e, v in rows]

    if comp.is_settled:
        payloads.sort(key=lambda x: (x["final_rank"] or 9999, x["id"]))
    elif sort == "latest":
        payloads.sort(key=lambda x: x["submitted_at"] or "", reverse=True)
    elif sort == "score":
        payloads.sort(
            key=lambda x: ((x["video"] or {}).get("ai_score") or 0),
            reverse=True,
        )
    else:
        payloads.sort(key=lambda x: (-x["votes"], x["id"]))

    total = len(payloads)
    start = (page - 1) * page_size
    return {
        "items": payloads[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{competition_id}/my-videos")
async def my_eligible_videos(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    comp = await db.get(JumpCompetition, competition_id)
    if not comp or not comp.is_published:
        raise HTTPException(status_code=404, detail="比赛不存在")

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
        data["eligible"] = True
        data["reason"] = ""
        items.append(data)
    return {"items": items, "submission_open": submission_open(comp)}


@router.post("/{competition_id}/submit")
async def submit_entry(
    competition_id: int,
    payload: SubmitIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    comp = await db.get(JumpCompetition, competition_id)
    if not comp or not comp.is_published:
        raise HTTPException(status_code=404, detail="比赛不存在")
    if not submission_open(comp):
        raise HTTPException(status_code=400, detail="当前不在投稿窗口内")

    existing = (
        await db.execute(
            select(CompetitionEntry).where(
                CompetitionEntry.competition_id == competition_id,
                CompetitionEntry.username == user.username,
                CompetitionEntry.status == "active",
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="每场比赛只能投稿一个视频")

    video = await db.get(JumpVideo, payload.video_id)
    if not video or video.username != user.username:
        raise HTTPException(status_code=404, detail="视频不存在")
    if not video.is_public or video.score_status != "done":
        raise HTTPException(status_code=400, detail="请投稿已公开且分析完成的视频")

    entry = CompetitionEntry(
        competition_id=competition_id,
        video_id=video.id,
        username=user.username,
        status="active",
    )
    db.add(entry)
    try:
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"投稿失败：{exc}") from exc
    await db.refresh(entry)
    return await _entry_payload(db, entry, video, viewer=user)


@router.post("/{competition_id}/entries/{entry_id}/vote")
async def vote_entry(
    competition_id: int,
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    comp = await db.get(JumpCompetition, competition_id)
    if not comp or not comp.is_published:
        raise HTTPException(status_code=404, detail="比赛不存在")
    if not voting_open(comp):
        raise HTTPException(status_code=400, detail="当前不在投票窗口内")

    entry = await db.get(CompetitionEntry, entry_id)
    if not entry or entry.competition_id != competition_id or entry.status != "active":
        raise HTTPException(status_code=404, detail="作品不存在")

    existing = (
        await db.execute(
            select(CompetitionVote).where(
                CompetitionVote.entry_id == entry_id,
                CompetitionVote.username == user.username,
            )
        )
    ).scalar_one_or_none()
    if not existing:
        db.add(
            CompetitionVote(
                competition_id=competition_id,
                entry_id=entry_id,
                username=user.username,
            )
        )
        await db.commit()

    votes = await count_votes(db, entry_id)
    return {"ok": True, "votes": votes}


@router.post("/{competition_id}/entries/{entry_id}/report")
async def report_entry(
    competition_id: int,
    entry_id: int,
    payload: ReportIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = await db.get(CompetitionEntry, entry_id)
    if not entry or entry.competition_id != competition_id:
        raise HTTPException(status_code=404, detail="作品不存在")
    existing = (
        await db.execute(
            select(CompetitionReport).where(
                CompetitionReport.entry_id == entry_id,
                CompetitionReport.username == user.username,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return {"ok": True, "already": True}
    db.add(
        CompetitionReport(
            competition_id=competition_id,
            entry_id=entry_id,
            username=user.username,
            reason=(payload.reason or "").strip()[:500],
            status="pending",
        )
    )
    await db.commit()
    return {"ok": True}
