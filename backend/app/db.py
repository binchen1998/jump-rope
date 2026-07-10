from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import DB_TYPE, async_db_url

engine = create_async_engine(
    async_db_url(),
    echo=False,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DB_TYPE == "sqlite" else {},
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def close_db() -> None:
    await engine.dispose()
