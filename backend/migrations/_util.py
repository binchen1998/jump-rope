"""迁移脚本公共工具（同步 SQLAlchemy 连接）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

from app.config import DB_TYPE, sync_db_url  # noqa: E402


def get_engine():
    return create_engine(sync_db_url())


def has_table(conn, name: str) -> bool:
    return inspect(conn).has_table(name)


def last_insert_id(conn) -> int:
    if DB_TYPE == "mysql":
        return conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    return conn.execute(text("SELECT last_insert_rowid()")).scalar()
