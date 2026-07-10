from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(50), default="")
    avatar: Mapped[str] = mapped_column(String(16), default="跳绳")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JumpVideo(Base):
    """用户上传的跳绳视频（每日限 1 条）。"""

    __tablename__ = "jump_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")

    video_url: Mapped[str] = mapped_column(Text, default="")
    video_key: Mapped[str] = mapped_column(String(500), default="")
    cover_url: Mapped[str] = mapped_column(Text, default="")
    local_path: Mapped[str] = mapped_column(Text, default="")

    # pending | processing | ready | failed
    media_status: Mapped[str] = mapped_column(String(20), default="pending")
    media_error: Mapped[str] = mapped_column(Text, default="")

    # pending | processing | done | failed
    score_status: Mapped[str] = mapped_column(String(20), default="pending")
    score_error: Mapped[str] = mapped_column(Text, default="")

    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    jump_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    speed_per_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    fancy_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fancy_duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_score_detail: Mapped[str] = mapped_column(Text, default="")  # JSON

    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # YYYY-MM-DD（中国时区），用于每日上传限额
    upload_date: Mapped[str] = mapped_column(String(10), index=True, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class FeaturedVideo(Base):
    __tablename__ = "featured_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("jump_videos.id"), unique=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(20), default="admin")  # admin | submission
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeaturedSubmission(Base):
    __tablename__ = "featured_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("jump_videos.id"), index=True)
    username: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | approved | rejected
    reject_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class JumpCompetition(Base):
    __tablename__ = "jump_competitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str] = mapped_column(Text, default="")

    start_date: Mapped[date] = mapped_column(Date)
    submission_deadline: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)

    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    is_settled: Mapped[bool] = mapped_column(Boolean, default=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    entries: Mapped[list["CompetitionEntry"]] = relationship(back_populates="competition")


class CompetitionEntry(Base):
    __tablename__ = "competition_entries"
    __table_args__ = (
        UniqueConstraint("competition_id", "username", name="uq_comp_entry_user"),
        UniqueConstraint("competition_id", "video_id", name="uq_comp_entry_video"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("jump_competitions.id"), index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("jump_videos.id"), index=True)
    username: Mapped[str] = mapped_column(String(50), index=True)

    status: Mapped[str] = mapped_column(String(20), default="active")  # active | removed
    removal_reason: Mapped[str] = mapped_column(Text, default="")
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    final_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_votes: Mapped[int] = mapped_column(Integer, default=0)

    competition: Mapped["JumpCompetition"] = relationship(back_populates="entries")
    votes: Mapped[list["CompetitionVote"]] = relationship(back_populates="entry")


class CompetitionVote(Base):
    __tablename__ = "competition_votes"
    __table_args__ = (UniqueConstraint("entry_id", "username", name="uq_comp_vote_entry_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("jump_competitions.id"), index=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("competition_entries.id"), index=True)
    username: Mapped[str] = mapped_column(String(50), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    entry: Mapped["CompetitionEntry"] = relationship(back_populates="votes")


class CompetitionReport(Base):
    __tablename__ = "competition_reports"
    __table_args__ = (UniqueConstraint("entry_id", "username", name="uq_comp_report_entry_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("jump_competitions.id"), index=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("competition_entries.id"), index=True)
    username: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | deleted
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
