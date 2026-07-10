import asyncio
import logging
import os
import signal
from pathlib import Path

from app.backup_database import backup_storage_enabled, log_backup_storage_status
from app.database_backup_worker import database_backup_worker
from app.db import close_db
from app.workers import score_worker, settle_worker, transcode_worker

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
WORKER_LOCK_PATH = BASE_DIR / ".background-workers.lock"


class BackgroundWorkerLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.handle.seek(0)
            self.handle.truncate()
            self.handle.write(str(os.getpid()).encode("ascii"))
            self.handle.flush()
            return True
        except OSError:
            self.release()
            return False

    def release(self) -> None:
        if not self.handle:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self.handle.close()
        self.handle = None


async def run_background_workers() -> None:
    log_backup_storage_status(logger.info)
    if backup_storage_enabled():
        logger.info("database backup worker enabled")
    else:
        logger.info("database backup worker will idle (qiniu backup storage not ready)")

    stop_event = asyncio.Event()
    worker_lock = BackgroundWorkerLock(WORKER_LOCK_PATH)
    if not worker_lock.acquire():
        logger.warning("background workers already running on this host, exiting")
        return

    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        stop_event.set()

    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, RuntimeError):
            pass

    worker_tasks = [
        asyncio.create_task(transcode_worker(stop_event), name="transcode"),
        asyncio.create_task(score_worker(stop_event), name="score"),
        asyncio.create_task(settle_worker(stop_event), name="settle"),
        asyncio.create_task(database_backup_worker(stop_event), name="db-backup"),
    ]
    logger.info("background workers started: transcode/score/settle/db-backup")

    try:
        await stop_event.wait()
    finally:
        stop_event.set()
        for task in worker_tasks:
            task.cancel()
        for task in worker_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        worker_lock.release()
        await close_db()
