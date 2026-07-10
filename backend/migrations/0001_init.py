"""0001 初始化表结构。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Base  # noqa: E402
from app import models  # noqa: F401,E402
from migrations._util import get_engine  # noqa: E402


def upgrade() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("0001_init: tables created")


if __name__ == "__main__":
    upgrade()
