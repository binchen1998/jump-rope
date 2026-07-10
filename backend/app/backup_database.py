"""全量备份当前数据库（SQLite / MySQL），可选上传七牛私有 bucket。"""

import argparse
import gzip
import os
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    from qiniu import Auth, BucketManager, put_file
except ImportError:  # pragma: no cover
    Auth = None
    BucketManager = None
    put_file = None
from sqlalchemy.engine import make_url

from .config import (
    BASE_DIR,
    DB_BACKUP_KEEP_LOCAL,
    DB_BACKUP_OUTPUT_DIR,
    DB_TYPE,
    MYSQL_URL,
    QINIU_BACKUP_PREFIX,
    QINIU_BACKUP_SLOTS,
    SQLITE_FILE,
)

PROGRESS_INTERVAL_SECONDS = 2.0
DEFAULT_OUTPUT_DIR = DB_BACKUP_OUTPUT_DIR
QINIU_ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY", "").strip()
QINIU_SECRET_KEY = os.getenv("QINIU_SECRET_KEY", "").strip()
QINIU_BACKUP_BUCKET = "binchen-private"


def _format_bytes(num_bytes: int | float) -> str:
    value = float(num_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _print_progress(message: str) -> None:
    print(message, flush=True)


def backup_storage_ready() -> tuple[bool, str | None]:
    if not QINIU_ACCESS_KEY or not QINIU_SECRET_KEY:
        return False, "缺少 QINIU_ACCESS_KEY / QINIU_SECRET_KEY，已跳过数据库备份上传"
    if Auth is None or BucketManager is None or put_file is None:
        return False, "缺少 qiniu Python SDK，已跳过数据库备份上传"
    return True, None


def backup_storage_enabled() -> bool:
    ready, _ = backup_storage_ready()
    return ready


def log_backup_storage_status(print_fn=_print_progress) -> None:
    ready, reason = backup_storage_ready()
    if ready:
        print_fn(
            "数据库备份上传已启用: "
            f"bucket={QINIU_BACKUP_BUCKET} prefix={QINIU_BACKUP_PREFIX} slots={QINIU_BACKUP_SLOTS}"
        )
    else:
        print_fn(reason or "数据库备份上传未启用")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="全量备份当前数据库并输出进度。")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"备份输出目录，默认 {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--gzip",
        action="store_true",
        help="对输出文件进行 gzip 压缩。",
    )
    return parser


def _ensure_output_dir(path_str: str) -> Path:
    path = Path(path_str)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_backup_args(
    *,
    output_dir: str | None = None,
    gzip_enabled: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        output_dir=output_dir or DEFAULT_OUTPUT_DIR,
        gzip=gzip_enabled,
    )


def _backup_slot_index(when: datetime | None = None) -> int:
    backup_time = when or datetime.now()
    return ((backup_time.toordinal() - 1) % QINIU_BACKUP_SLOTS) + 1


def _backup_object_key(slot_index: int, source_path: Path) -> str:
    suffix = "".join(source_path.suffixes) or ".bak"
    return f"{QINIU_BACKUP_PREFIX}/backup-slot-{slot_index}{suffix}"


def _sqlite_file_path() -> Path:
    db_path = Path(SQLITE_FILE)
    if not db_path.is_absolute():
        db_path = (BASE_DIR / db_path).resolve()
    return db_path


def _sqlite_backup(args: argparse.Namespace) -> Path:
    source_path = _sqlite_file_path()
    if not source_path.exists():
        raise RuntimeError(f"SQLite 数据库文件不存在: {source_path}")

    output_dir = _ensure_output_dir(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_name = f"math-sqlite-backup-{timestamp}.sqlite3"
    dest_path = output_dir / base_name
    final_path = dest_path.with_suffix(dest_path.suffix + ".gz") if args.gzip else dest_path

    source_size = source_path.stat().st_size
    _print_progress(
        f"开始备份 SQLite 数据库: {source_path} -> {final_path}，源文件大小约 {_format_bytes(source_size)}"
    )

    src_conn = sqlite3.connect(str(source_path))
    dst_conn = sqlite3.connect(str(dest_path))

    page_size = src_conn.execute("PRAGMA page_size").fetchone()[0]
    page_count = src_conn.execute("PRAGMA page_count").fetchone()[0]
    total_bytes = page_size * page_count
    started_at = time.time()

    def progress(status: int, remaining: int, total: int) -> None:
        done = total - remaining
        percent = 100.0 if total <= 0 else (done / total) * 100
        copied_bytes = done * page_size
        elapsed = max(time.time() - started_at, 0.001)
        speed = copied_bytes / elapsed
        _print_progress(
            "SQLite 备份进度: "
            f"{percent:5.1f}% "
            f"({done}/{total} pages, {_format_bytes(copied_bytes)}/{_format_bytes(total_bytes)}) "
            f"速度 {_format_bytes(speed)}/s"
        )

    try:
        src_conn.backup(dst_conn, pages=2048, progress=progress, sleep=0.05)
    finally:
        dst_conn.close()
        src_conn.close()

    if args.gzip:
        _print_progress(f"开始压缩备份文件: {dest_path} -> {final_path}")
        _gzip_with_progress(dest_path, final_path)
        dest_path.unlink()

    elapsed = max(time.time() - started_at, 0.001)
    _print_progress(
        f"SQLite 备份完成: {final_path}，总耗时 {elapsed:.1f}s，最终大小 {_format_bytes(final_path.stat().st_size)}"
    )
    return final_path


def _gzip_with_progress(source_path: Path, dest_path: Path) -> None:
    total_size = source_path.stat().st_size
    copied = 0
    started_at = time.time()
    last_report = 0.0

    with source_path.open("rb") as src, gzip.open(dest_path, "wb") as dst:
        while True:
            chunk = src.read(8 * 1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)
            copied += len(chunk)
            now = time.time()
            if now - last_report >= PROGRESS_INTERVAL_SECONDS:
                last_report = now
                percent = 100.0 if total_size <= 0 else (copied / total_size) * 100
                elapsed = max(now - started_at, 0.001)
                speed = copied / elapsed
                _print_progress(
                    "压缩进度: "
                    f"{percent:5.1f}% "
                    f"({_format_bytes(copied)}/{_format_bytes(total_size)}) "
                    f"速度 {_format_bytes(speed)}/s"
                )


def _mysql_estimated_size_bytes(url_str: str) -> int:
    url = make_url(url_str)
    if not url.database:
        raise RuntimeError("MYSQL_URL 缺少数据库名")

    cmd = ["mysql", "-N", "-B"]
    if url.host:
        cmd.extend(["-h", str(url.host)])
    if url.port:
        cmd.extend(["-P", str(url.port)])
    if url.username:
        cmd.extend(["-u", str(url.username)])
    cmd.extend(
        [
            "-e",
            (
                "SELECT COALESCE(SUM(data_length + index_length), 0) "
                "FROM information_schema.tables "
                f"WHERE table_schema = '{url.database}'"
            ),
        ]
    )

    env = os.environ.copy()
    env["MYSQL_PWD"] = str(url.password or "")
    result = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "执行 mysql 估算数据库大小失败"
            + (f": {result.stderr.strip()}" if result.stderr.strip() else "")
        )

    output = (result.stdout or "").strip()
    if not output:
        return 0
    return int(output)


def _mysql_dump_command(url_str: str) -> tuple[list[str], str]:
    url = make_url(url_str)
    if not url.database:
        raise RuntimeError("MYSQL_URL 缺少数据库名")

    cmd = ["mysqldump"]
    if url.host:
        cmd.extend(["-h", str(url.host)])
    if url.port:
        cmd.extend(["-P", str(url.port)])
    if url.username:
        cmd.extend(["-u", str(url.username)])

    cmd.extend(
        [
            "--single-transaction",
            "--quick",
            "--routines",
            "--events",
            "--triggers",
            "--default-character-set=utf8mb4",
            "--hex-blob",
            str(url.database),
        ]
    )
    return cmd, str(url.password or "")


def _mysql_backup(args: argparse.Namespace) -> Path:
    if not MYSQL_URL:
        raise RuntimeError("缺少 MYSQL_URL")

    output_dir = _ensure_output_dir(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_name = f"math-mysql-backup-{timestamp}.sql"
    dest_path = output_dir / base_name
    final_path = dest_path.with_suffix(dest_path.suffix + ".gz") if args.gzip else dest_path

    cmd, password = _mysql_dump_command(MYSQL_URL)
    env = os.environ.copy()
    env["MYSQL_PWD"] = password

    _print_progress("开始估算 MySQL 数据库大小...")
    estimated_size = _mysql_estimated_size_bytes(MYSQL_URL)
    if estimated_size > 0:
        _print_progress(f"MySQL 估算数据量约 {_format_bytes(estimated_size)}")
    else:
        _print_progress("未能估算 MySQL 数据量，将只显示已写入大小和速度")

    _print_progress(f"开始全量导出 MySQL 到 {final_path}")
    started_at = time.time()
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    if process.stdout is None or process.stderr is None:
        raise RuntimeError("mysqldump 未返回可读输出流")

    target_handle = gzip.open(final_path, "wb") if args.gzip else final_path.open("wb")
    last_report = 0.0
    bytes_written = 0
    stderr_chunks: list[bytes] = []

    def stderr_reader() -> None:
        while True:
            chunk = process.stderr.read(4096)
            if not chunk:
                break
            stderr_chunks.append(chunk)

    stderr_thread = threading.Thread(target=stderr_reader, daemon=True)
    stderr_thread.start()

    try:
        while True:
            chunk = process.stdout.read(8 * 1024 * 1024)
            if not chunk:
                break
            target_handle.write(chunk)
            bytes_written += len(chunk)

            now = time.time()
            if now - last_report >= PROGRESS_INTERVAL_SECONDS:
                last_report = now
                elapsed = max(now - started_at, 0.001)
                speed = bytes_written / elapsed
                if estimated_size > 0:
                    percent = min((bytes_written / estimated_size) * 100, 99.0)
                    _print_progress(
                        "MySQL 备份进度: "
                        f"{percent:5.1f}% "
                        f"(已写入 {_format_bytes(bytes_written)} / 估算 {_format_bytes(estimated_size)}) "
                        f"速度 {_format_bytes(speed)}/s"
                    )
                else:
                    _print_progress(
                        "MySQL 备份进度: "
                        f"已写入 {_format_bytes(bytes_written)} "
                        f"速度 {_format_bytes(speed)}/s"
                    )
    finally:
        target_handle.close()

    return_code = process.wait()
    stderr_thread.join(timeout=2)
    stderr_text = b"".join(stderr_chunks).decode("utf-8", errors="replace").strip()

    if return_code != 0:
        if final_path.exists():
            final_path.unlink()
        raise RuntimeError(
            f"mysqldump 失败，exit_code={return_code}"
            + (f"，stderr={stderr_text}" if stderr_text else "")
        )

    elapsed = max(time.time() - started_at, 0.001)
    _print_progress(
        f"MySQL 备份完成: {final_path}，总耗时 {elapsed:.1f}s，最终大小 {_format_bytes(final_path.stat().st_size)}"
    )
    return final_path


def backup_current_database(
    *,
    output_dir: str | None = None,
    gzip_enabled: bool = False,
) -> Path:
    args = _build_backup_args(output_dir=output_dir, gzip_enabled=gzip_enabled)
    if DB_TYPE == "sqlite":
        return _sqlite_backup(args)
    if DB_TYPE == "mysql":
        return _mysql_backup(args)
    raise RuntimeError(f"不支持的 DB_TYPE: {DB_TYPE}")


def upload_backup_file_to_qiniu(
    source_path: Path,
    *,
    slot_index: int,
) -> str:
    ready, reason = backup_storage_ready()
    if not ready:
        raise RuntimeError(reason or "七牛备份未就绪")

    auth = Auth(QINIU_ACCESS_KEY, QINIU_SECRET_KEY)
    key = _backup_object_key(slot_index, source_path)
    bucket = BucketManager(auth)
    ret, info = bucket.delete(QINIU_BACKUP_BUCKET, key)
    status_code = getattr(info, "status_code", None)
    if status_code not in (200, 612):
        raise RuntimeError(f"删除旧数据库备份失败，status={status_code}, ret={ret}")

    upload_token = auth.upload_token(QINIU_BACKUP_BUCKET, key, 3600)
    ret, info = put_file(upload_token, key, str(source_path))

    status_code = getattr(info, "status_code", None)
    if status_code is not None and status_code >= 300:
        raise RuntimeError(f"上传数据库备份到七牛失败，status={status_code}, ret={ret}")
    if ret is None:
        raise RuntimeError("上传数据库备份到七牛失败，返回为空")

    return key


def backup_database_to_qiniu_once(
    *,
    output_dir: str | None = None,
    gzip_enabled: bool = True,
    when: datetime | None = None,
    slot_index: int | None = None,
    keep_local: bool | None = None,
) -> dict:
    backup_time = when or datetime.now()
    final_path = backup_current_database(
        output_dir=output_dir,
        gzip_enabled=gzip_enabled,
    )
    resolved_slot_index = slot_index or _backup_slot_index(backup_time)
    _print_progress(f"开始上传数据库备份到七牛，轮换槽位 slot={resolved_slot_index}")
    object_key = upload_backup_file_to_qiniu(final_path, slot_index=resolved_slot_index)
    _print_progress(
        f"数据库备份已上传到七牛: bucket={QINIU_BACKUP_BUCKET} key={object_key}"
    )

    should_keep_local = DB_BACKUP_KEEP_LOCAL if keep_local is None else keep_local
    if not should_keep_local:
        try:
            final_path.unlink()
            _print_progress(f"已删除本地临时备份文件: {final_path}")
        except OSError as exc:
            _print_progress(f"删除本地临时备份文件失败: {final_path} ({exc})")

    return {
        "slot_index": resolved_slot_index,
        "object_key": object_key,
        "backup_path": final_path,
        "backup_time": backup_time.isoformat(),
    }


def main() -> int:
    args = _build_parser().parse_args()

    try:
        final_path = backup_current_database(
            output_dir=args.output_dir,
            gzip_enabled=args.gzip,
        )
    except KeyboardInterrupt:
        _print_progress("备份已被手动中断")
        return 130
    except Exception as exc:
        _print_progress(f"备份失败: {type(exc).__name__}: {exc}")
        return 2

    _print_progress(f"备份文件已生成: {final_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
