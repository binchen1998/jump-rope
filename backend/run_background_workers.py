import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from background_workers import run_background_workers


def configure_worker_logging() -> Path:
    base_dir = Path(__file__).resolve().parent
    log_path = Path(
        os.getenv(
            "BACKGROUND_WORKER_LOG_PATH",
            str(base_dir / "logs" / "background-workers.log"),
        )
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    return log_path


if __name__ == "__main__":
    log_path = configure_worker_logging()
    logging.getLogger(__name__).info("background worker file logging enabled: path=%s", log_path)
    try:
        asyncio.run(run_background_workers())
    except KeyboardInterrupt:
        pass
