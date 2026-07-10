"""后台 Worker：转码上传 / AI 跳绳分析 / 比赛结算。"""

from __future__ import annotations

import logging
import traceback
import uuid
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .cdn import store_local_file
from .competition_utils import settle_competition_sync
from .config import (
    JUMP_AI_MODE,
    MAX_VIDEO_DURATION_SEC,
    MEDIA_DIR,
    SCORE_WORKER_INTERVAL_SECONDS,
    SETTLE_WORKER_INTERVAL_SECONDS,
    TRANSCODE_WORKER_INTERVAL_SECONDS,
    sync_db_url,
)
from .media_utils import extract_cover_jpg, ffmpeg_available, transcode_to_mp4
from .models import JumpCompetition, JumpVideo
from .scoring import analyze_jump_rope
from .time_utils import today_cn

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _get_session() -> Session:
    global _engine, _SessionLocal
    if _SessionLocal is None:
        _engine = create_engine(sync_db_url(), pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _SessionLocal()


def process_one_transcode(db: Session) -> bool:
    result = db.execute(
        select(JumpVideo)
        .where(JumpVideo.media_status == "pending")
        .order_by(JumpVideo.id.asc())
        .limit(1)
    )
    video = result.scalar_one_or_none()
    if not video:
        return False

    video.media_status = "processing"
    db.commit()
    try:
        if not ffmpeg_available():
            raise RuntimeError("未找到 ffmpeg，请先安装并加入 PATH")
        src = Path(video.local_path)
        if not src.exists():
            raise RuntimeError(f"staging 文件不存在: {src}")

        dst = MEDIA_DIR / "entries" / f"video_{video.id}_{uuid.uuid4().hex}.mp4"
        transcode_to_mp4(src, dst)
        url, key = store_local_file(
            local_path=dst,
            kind="entries",
            name=video.username or f"video{video.id}",
            ext="mp4",
            mime_type="video/mp4",
        )
        video.video_url = url
        video.video_key = key
        video.local_path = str(dst)

        cover = MEDIA_DIR / "covers" / f"cover_{video.id}.jpg"
        cover_path = extract_cover_jpg(dst, cover)
        if cover_path and cover_path.exists():
            try:
                cover_url, _ = store_local_file(
                    local_path=cover_path,
                    kind="covers",
                    name=f"video{video.id}",
                    ext="jpg",
                    mime_type="image/jpeg",
                )
                video.cover_url = cover_url
            except Exception as exc:  # noqa: BLE001
                logger.warning("upload cover failed: %s", exc)

        video.media_status = "ready"
        video.media_error = ""
        if video.score_status in ("pending", "failed"):
            video.score_status = "pending"
        db.commit()
        try:
            src.unlink(missing_ok=True)
        except OSError:
            pass
        logger.info("transcode ready video=%s", video.id)
    except Exception as exc:  # noqa: BLE001
        logger.error("transcode failed video=%s: %s", video.id, exc)
        video.media_status = "failed"
        video.media_error = str(exc)[:1500]
        db.commit()
    return True


def process_one_score(db: Session) -> bool:
    result = db.execute(
        select(JumpVideo)
        .where(
            JumpVideo.score_status == "pending",
            JumpVideo.media_status == "ready",
        )
        .order_by(JumpVideo.id.asc())
        .limit(1)
    )
    video = result.scalar_one_or_none()
    if not video:
        return False

    video.score_status = "processing"
    db.commit()
    try:
        local = Path(video.local_path)
        if not local.exists():
            raise RuntimeError("视频本地文件不存在")

        analysis = analyze_jump_rope(
            local,
            mode=JUMP_AI_MODE,
            max_duration_sec=float(MAX_VIDEO_DURATION_SEC),
        )
        if analysis.duration_sec > MAX_VIDEO_DURATION_SEC + 1:
            raise RuntimeError(f"视频超过 {MAX_VIDEO_DURATION_SEC} 秒限制")

        video.duration_sec = analysis.duration_sec
        video.jump_count = analysis.jump_count
        video.speed_per_min = analysis.speed_per_min
        video.fancy_count = analysis.fancy_count
        video.fancy_duration_sec = analysis.fancy_duration_sec
        video.ai_score = analysis.score
        video.ai_score_detail = analysis.to_json()
        video.score_status = "done"
        video.score_error = ""
        db.commit()
        logger.info(
            "score done video=%s jumps=%s speed=%s fancy=%s",
            video.id,
            analysis.jump_count,
            analysis.speed_per_min,
            analysis.fancy_count,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("score failed video=%s: %s\n%s", video.id, exc, traceback.format_exc()[-800:])
        video.score_status = "failed"
        video.score_error = str(exc)[:1500]
        db.commit()
    return True


def process_settle_due(db: Session) -> int:
    today = today_cn()
    result = db.execute(
        select(JumpCompetition).where(
            JumpCompetition.is_settled.is_(False),
            JumpCompetition.is_published.is_(True),
            JumpCompetition.end_date < today,
        )
    )
    count = 0
    for comp in result.scalars().all():
        settle_competition_sync(db, comp)
        count += 1
        logger.info("settled competition=%s", comp.id)
    return count


async def transcode_worker(stop_event) -> None:
    import asyncio

    while not stop_event.is_set():
        try:
            with _get_session() as db:
                while process_one_transcode(db):
                    if stop_event.is_set():
                        break
        except Exception as exc:  # noqa: BLE001
            logger.exception("transcode_worker error: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=TRANSCODE_WORKER_INTERVAL_SECONDS)
        except TimeoutError:
            pass


def _score_once() -> bool:
    with _get_session() as db:
        return process_one_score(db)


async def score_worker(stop_event) -> None:
    import asyncio

    while not stop_event.is_set():
        try:
            # 姿态分析是 CPU 密集任务，放线程池避免阻塞同进程其他 worker
            while await asyncio.to_thread(_score_once):
                if stop_event.is_set():
                    break
        except Exception as exc:  # noqa: BLE001
            logger.exception("score_worker error: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=SCORE_WORKER_INTERVAL_SECONDS)
        except TimeoutError:
            pass


async def settle_worker(stop_event) -> None:
    import asyncio

    while not stop_event.is_set():
        try:
            with _get_session() as db:
                process_settle_due(db)
        except Exception as exc:  # noqa: BLE001
            logger.exception("settle_worker error: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=SETTLE_WORKER_INTERVAL_SECONDS)
        except TimeoutError:
            pass
