import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(exist_ok=True)
(MEDIA_DIR / "entries").mkdir(exist_ok=True)
(MEDIA_DIR / "staging").mkdir(exist_ok=True)
(MEDIA_DIR / "covers").mkdir(exist_ok=True)

SQLITE_FILE = os.getenv("SQLITE_FILE", str(DATA_DIR / "app.db"))
MYSQL_URL = os.getenv("MYSQL_URL", "mysql+aiomysql://root:root@localhost:3306/jump_rope")


def async_db_url() -> str:
    if DB_TYPE == "mysql":
        return MYSQL_URL
    return f"sqlite+aiosqlite:///{SQLITE_FILE}"


def sync_db_url() -> str:
    if DB_TYPE == "mysql":
        return MYSQL_URL.replace("+aiomysql", "+pymysql")
    return f"sqlite:///{SQLITE_FILE}"


JWT_SECRET = os.getenv("JWT_SECRET", "jump_rope_jwt_secret_2026")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "coding61")
TOKEN_EXPIRE_DAYS = 365

# 视频限制
MAX_VIDEO_DURATION_SEC = int(os.getenv("MAX_VIDEO_DURATION_SEC", "120"))  # 2 分钟
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))  # 200MB
DAILY_UPLOAD_LIMIT = int(os.getenv("DAILY_UPLOAD_LIMIT", "1"))

# 七牛 CDN（前端 deploy + 媒体上传）
QINIU_ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY", "").strip()
QINIU_SECRET_KEY = os.getenv("QINIU_SECRET_KEY", "").strip()
QINIU_BUCKET = os.getenv("QINIU_BUCKET", "").strip()
QINIU_CDN_DOMAIN = (os.getenv("QINIU_CDN_DOMAIN") or "https://static1.cxy61.com").strip().rstrip("/")
QINIU_FRONTEND_PREFIX = (os.getenv("QINIU_FRONTEND_PREFIX") or "jump-rope").strip().strip("/")
QINIU_MEDIA_PREFIX = (os.getenv("QINIU_MEDIA_PREFIX") or "jump-rope-media").strip().strip("/")
QINIU_REGION = os.getenv("QINIU_REGION", "z0")
QINIU_UPLOAD_TOKEN_EXPIRES = int(os.getenv("QINIU_UPLOAD_TOKEN_EXPIRES", "3600"))

# 七牛数据库备份
QINIU_BACKUP_PREFIX = (os.getenv("QINIU_BACKUP_PREFIX", "jump-rope-backup") or "jump-rope-backup").strip()
QINIU_BACKUP_SLOTS = max(1, int(os.getenv("QINIU_BACKUP_SLOTS", "5")))
DB_BACKUP_SCHEDULE_HOUR = int(os.getenv("DB_BACKUP_SCHEDULE_HOUR", "2"))
DB_BACKUP_SCHEDULE_MINUTE = int(os.getenv("DB_BACKUP_SCHEDULE_MINUTE", "0"))
DB_BACKUP_RETRY_DELAY_SECONDS = max(60, int(os.getenv("DB_BACKUP_RETRY_DELAY_SECONDS", "1800")))
DB_BACKUP_OUTPUT_DIR = os.getenv("DB_BACKUP_OUTPUT_DIR", "/home/binch")
DB_BACKUP_KEEP_LOCAL = os.getenv("DB_BACKUP_KEEP_LOCAL", "0").strip().lower() in ("1", "true", "yes")

# Worker 轮询间隔
SCORE_WORKER_INTERVAL_SECONDS = max(5, int(os.getenv("SCORE_WORKER_INTERVAL_SECONDS", "10")))
SETTLE_WORKER_INTERVAL_SECONDS = max(30, int(os.getenv("SETTLE_WORKER_INTERVAL_SECONDS", "60")))
TRANSCODE_WORKER_INTERVAL_SECONDS = max(3, int(os.getenv("TRANSCODE_WORKER_INTERVAL_SECONDS", "5")))

# AI 分析：real=MediaPipe 姿态估计+计数（默认）；mock=启发式模拟（联调用）
JUMP_AI_MODE = os.getenv("JUMP_AI_MODE", "real").strip().lower()
