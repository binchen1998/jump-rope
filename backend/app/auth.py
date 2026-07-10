from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import unquote

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import ADMIN_PASSWORD, ADMIN_USERNAME, JWT_SECRET, TOKEN_EXPIRE_DAYS
from .db import get_db
from .models import User

ALGORITHM = "HS256"


def _sanitize_username(raw: str) -> str:
    name = unquote(raw or "").strip()
    return name[:50]


async def _get_or_create(db: AsyncSession, username: str) -> User:
    user = await db.get(User, username)
    if user is not None:
        return user
    user = User(username=username, nickname=username, avatar="跳绳")
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
        return user
    except IntegrityError:
        await db.rollback()
        user = await db.get(User, username)
        if user is None:
            raise
        return user


async def get_current_user(
    x_username: Optional[str] = Header(None, alias="X-Username"),
    db: AsyncSession = Depends(get_db),
) -> User:
    username = _sanitize_username(x_username) if x_username else ""
    if not username:
        raise HTTPException(status_code=401, detail="缺少用户身份（X-Username）")
    return await _get_or_create(db, username)


async def get_optional_user(
    x_username: Optional[str] = Header(None, alias="X-Username"),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    username = _sanitize_username(x_username) if x_username else ""
    if not username:
        return None
    return await _get_or_create(db, username)


def create_admin_token() -> str:
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": ADMIN_USERNAME, "role": "admin", "exp": expire},
        JWT_SECRET,
        algorithm=ALGORITHM,
    )


def verify_admin_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload.get("sub") == ADMIN_USERNAME or payload.get("role") == "admin"
    except JWTError:
        return False


def check_admin_credentials(username: str, password: str) -> bool:
    return username.strip() == ADMIN_USERNAME and password == ADMIN_PASSWORD


def check_admin_password(password: str) -> bool:
    """兼容仅密码登录。"""
    return password == ADMIN_PASSWORD


async def require_admin(authorization: Optional[str] = Header(None)) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="需要管理员权限")
    if not verify_admin_token(authorization[7:]):
        raise HTTPException(status_code=401, detail="管理员令牌无效或已过期")
    return True
