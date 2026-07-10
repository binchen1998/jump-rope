"""定时数据库备份（mysqldump / SQLite → 七牛轮换槽位，由 background_workers 进程运行）。"""

import asyncio
import json
import logging
from datetime import datetime, timedelta

from .backup_database import (
    QINIU_BACKUP_SLOTS,
    backup_database_to_qiniu_once,
    backup_storage_enabled,
)
from .config import (
    BASE_DIR,
    DB_BACKUP_SCHEDULE_HOUR,
    DB_BACKUP_SCHEDULE_MINUTE,
    DB_BACKUP_RETRY_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)

DATABASE_BACKUP_STATE_PATH = BASE_DIR / ".database-backup-state.json"


def _load_database_backup_state() -> dict:
    try:
        return json.loads(DATABASE_BACKUP_STATE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        logger.warning("failed to load database backup worker state", exc_info=True)
        return {}


def _save_database_backup_state(state: dict) -> None:
    DATABASE_BACKUP_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _scheduled_backup_time_for(day: datetime) -> datetime:
    return day.replace(
        hour=DB_BACKUP_SCHEDULE_HOUR,
        minute=DB_BACKUP_SCHEDULE_MINUTE,
        second=0,
        microsecond=0,
    )


def _next_scheduled_backup_time(now: datetime) -> datetime:
    candidate = _scheduled_backup_time_for(now)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _next_backup_slot_index(state: dict) -> int:
    try:
        last_slot_index = int(state.get("last_slot_index") or 0)
    except (TypeError, ValueError):
        last_slot_index = 0
    return (last_slot_index % QINIU_BACKUP_SLOTS) + 1


async def database_backup_worker(stop_event: asyncio.Event) -> None:
    if not backup_storage_enabled():
        logger.info("database backup worker disabled because qiniu backup storage is not ready")
        await stop_event.wait()
        return

    next_retry_at: datetime | None = None
    last_sleep_target: str | None = None

    while not stop_event.is_set():
        now = datetime.now()
        state = _load_database_backup_state()
        last_success_date = str(state.get("last_success_date") or "")
        scheduled_today = _scheduled_backup_time_for(now)
        today_key = scheduled_today.date().isoformat()

        if now >= scheduled_today and last_success_date != today_key:
            target = next_retry_at if next_retry_at is not None and now < next_retry_at else now
        else:
            target = _next_scheduled_backup_time(now)
            next_retry_at = None

        if target > now:
            target_key = target.isoformat(timespec="seconds")
            if target_key != last_sleep_target:
                logger.info(
                    "database backup sleeping until %s (schedule=%02d:%02d)",
                    target_key,
                    DB_BACKUP_SCHEDULE_HOUR,
                    DB_BACKUP_SCHEDULE_MINUTE,
                )
                last_sleep_target = target_key
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=max((target - now).total_seconds(), 1),
                )
                break
            except asyncio.TimeoutError:
                pass
            continue

        last_sleep_target = None
        try:
            slot_index = _next_backup_slot_index(state)
            stats = await asyncio.to_thread(
                backup_database_to_qiniu_once,
                when=scheduled_today,
                gzip_enabled=True,
                slot_index=slot_index,
            )
            state.update(
                {
                    "last_success_date": today_key,
                    "last_backup_time": stats["backup_time"],
                    "last_slot_index": stats["slot_index"],
                    "last_object_key": stats["object_key"],
                    "slots": QINIU_BACKUP_SLOTS,
                }
            )
            _save_database_backup_state(state)
            next_retry_at = None
            logger.info(
                "database backup finished: slot=%s key=%s backup_time=%s",
                stats["slot_index"],
                stats["object_key"],
                stats["backup_time"],
            )
        except Exception:
            next_retry_at = datetime.now() + timedelta(seconds=DB_BACKUP_RETRY_DELAY_SECONDS)
            logger.exception(
                "database backup failed, will retry at %s",
                next_retry_at.isoformat(timespec="seconds"),
            )
