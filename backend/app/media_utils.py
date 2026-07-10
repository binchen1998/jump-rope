"""ffmpeg / 媒体处理工具。"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def run_ffmpeg(args: list[str], *, timeout: int = 600) -> None:
    cmd = ["ffmpeg", "-y", *args]
    logger.info("ffmpeg: %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-2000:]
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {err}")


def extract_audio_wav(video_path: str | Path, wav_path: str | Path, *, sample_rate: int = 22050) -> Path:
    video_path = Path(video_path)
    wav_path = Path(wav_path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            str(wav_path),
        ]
    )
    return wav_path


def transcode_to_mp4(src_path: str | Path, dst_path: str | Path) -> Path:
    src_path = Path(src_path)
    dst_path = Path(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-i",
            str(src_path),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(dst_path),
        ]
    )
    return dst_path


def extract_cover_jpg(video_path: str | Path, jpg_path: str | Path) -> Path | None:
    video_path = Path(video_path)
    jpg_path = Path(jpg_path)
    jpg_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_ffmpeg(
            [
                "-i",
                str(video_path),
                "-ss",
                "1",
                "-vframes",
                "1",
                "-q:v",
                "3",
                str(jpg_path),
            ]
        )
        return jpg_path if jpg_path.exists() else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("extract cover failed: %s", exc)
        return None
