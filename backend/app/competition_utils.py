"""比赛状态与结算工具。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from .models import CompetitionEntry, CompetitionVote, JumpCompetition
from .time_utils import today_cn

__all__ = [
    "competition_status",
    "submission_open",
    "voting_open",
    "serialize_competition",
    "count_votes",
    "count_votes_sync",
    "settle_competition_sync",
    "settle_competition",
    "today_cn",
]


def competition_status(comp: JumpCompetition) -> str:
    if comp.is_settled:
        return "ended"
    today = today_cn()
    if today < comp.start_date:
        return "upcoming"
    if today > comp.end_date:
        return "settling"
    return "live"


def submission_open(comp: JumpCompetition) -> bool:
    if not comp.is_published or comp.is_settled:
        return False
    today = today_cn()
    return comp.start_date <= today <= comp.submission_deadline


def voting_open(comp: JumpCompetition) -> bool:
    return competition_status(comp) == "live"


def serialize_competition(comp: JumpCompetition) -> dict:
    status = competition_status(comp)
    return {
        "id": comp.id,
        "title": comp.title,
        "description": comp.description or "",
        "cover_url": comp.cover_url or "",
        "start_date": comp.start_date.isoformat(),
        "submission_deadline": comp.submission_deadline.isoformat(),
        "end_date": comp.end_date.isoformat(),
        "is_published": comp.is_published,
        "is_settled": comp.is_settled,
        "settled_at": comp.settled_at.isoformat() if comp.settled_at else None,
        "status": status,
        "submission_open": submission_open(comp),
        "voting_open": voting_open(comp),
        "created_at": comp.created_at.isoformat() if comp.created_at else None,
    }


async def count_votes(db: AsyncSession, entry_id: int) -> int:
    r = await db.execute(
        select(func.count()).select_from(CompetitionVote).where(CompetitionVote.entry_id == entry_id)
    )
    return int(r.scalar() or 0)


def count_votes_sync(db: Session, entry_id: int) -> int:
    r = db.execute(
        select(func.count()).select_from(CompetitionVote).where(CompetitionVote.entry_id == entry_id)
    )
    return int(r.scalar() or 0)


def settle_competition_sync(db: Session, comp: JumpCompetition) -> bool:
    """按票数结算；乐观锁防重复。"""
    result = db.execute(
        update(JumpCompetition)
        .where(JumpCompetition.id == comp.id, JumpCompetition.is_settled.is_(False))
        .values(is_settled=True, settled_at=datetime.utcnow())
    )
    if result.rowcount == 0:
        return False

    entries = (
        db.execute(
            select(CompetitionEntry).where(
                CompetitionEntry.competition_id == comp.id,
                CompetitionEntry.status == "active",
            )
        )
        .scalars()
        .all()
    )
    ranked = []
    for entry in entries:
        votes = count_votes_sync(db, entry.id)
        ranked.append((entry, votes))
    ranked.sort(key=lambda x: (-x[1], x[0].submitted_at or datetime.utcnow(), x[0].id))
    for i, (entry, votes) in enumerate(ranked, start=1):
        entry.final_rank = i
        entry.final_votes = votes
    db.commit()
    return True


async def settle_competition(db: AsyncSession, comp: JumpCompetition) -> bool:
    result = await db.execute(
        update(JumpCompetition)
        .where(JumpCompetition.id == comp.id, JumpCompetition.is_settled.is_(False))
        .values(is_settled=True, settled_at=datetime.utcnow())
    )
    if result.rowcount == 0:
        return False

    entries = (
        await db.execute(
            select(CompetitionEntry).where(
                CompetitionEntry.competition_id == comp.id,
                CompetitionEntry.status == "active",
            )
        )
    ).scalars().all()
    ranked = []
    for entry in entries:
        votes = await count_votes(db, entry.id)
        ranked.append((entry, votes))
    ranked.sort(key=lambda x: (-x[1], x[0].submitted_at or datetime.utcnow(), x[0].id))
    for i, (entry, votes) in enumerate(ranked, start=1):
        entry.final_rank = i
        entry.final_votes = votes
    await db.commit()
    return True
