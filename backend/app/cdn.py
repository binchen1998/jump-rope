"""七牛 CDN 上传（参考视频 / 学生作品）。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path

from .config import (
    MEDIA_DIR,
    QINIU_ACCESS_KEY,
    QINIU_BUCKET,
    QINIU_CDN_DOMAIN,
    QINIU_MEDIA_PREFIX,
    QINIU_SECRET_KEY,
    QINIU_UPLOAD_TOKEN_EXPIRES,
)

try:
    from qiniu import Auth, put_data, put_file
except ImportError:  # pragma: no cover
    Auth = None
    put_file = None
    put_data = None

logger = logging.getLogger(__name__)


class CdnError(RuntimeError):
    pass


def cdn_ready() -> tuple[bool, str | None]:
    if not all([QINIU_ACCESS_KEY, QINIU_SECRET_KEY, QINIU_BUCKET, QINIU_CDN_DOMAIN]):
        return False, "七牛未配置完整"
    if Auth is None or put_file is None or put_data is None:
        return False, "缺少 qiniu Python SDK"
    return True, None


def cdn_enabled() -> bool:
    ready, _ = cdn_ready()
    return ready


def _normalized_domain() -> str:
    domain = QINIU_CDN_DOMAIN.rstrip("/")
    if domain and "://" not in domain:
        domain = f"https://{domain}"
    return domain


def public_cdn_url_for_key(key: str) -> str:
    return f"{_normalized_domain()}/{key.lstrip('/')}"


def safe_name(name: str) -> str:
    raw = (name or "").strip().replace("/", "_").replace("\\", "_")
    return raw[:80] if raw else "item"


def build_media_key(kind: str, name: str, ext: str) -> str:
    prefix = QINIU_MEDIA_PREFIX or "sing-media"
    safe_ext = (ext or "mp4").strip().lower().lstrip(".") or "mp4"
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    uid = uuid.uuid4().hex[:10]
    return f"{prefix}/{kind}/{safe_name(name)}/{stamp}_{uid}.{safe_ext}"


def upload_local_file(*, local_path: str | Path, key: str, mime_type: str | None = None) -> str:
    ready, reason = cdn_ready()
    if not ready:
        raise CdnError(reason or "七牛未就绪")

    auth = Auth(QINIU_ACCESS_KEY, QINIU_SECRET_KEY)
    upload_token = auth.upload_token(QINIU_BUCKET, key, QINIU_UPLOAD_TOKEN_EXPIRES)
    path = str(local_path)
    if mime_type:
        ret, info = put_file(upload_token, key, path, mime_type=mime_type)
    else:
        ret, info = put_file(upload_token, key, path)

    status_code = getattr(info, "status_code", None)
    if status_code is not None and status_code >= 300:
        raise CdnError(f"上传七牛失败，status={status_code}, ret={ret}")
    if ret is None:
        raise CdnError("上传七牛失败，返回为空")

    url = public_cdn_url_for_key(key)
    logger.info("七牛上传成功: key=%s url=%s", key, url)
    return url


def save_local_media(*, data: bytes, kind: str, name: str, ext: str) -> tuple[str, str]:
    """本地降级存储，返回 (relative_url, absolute_path)。"""
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    uid = uuid.uuid4().hex[:10]
    safe_ext = (ext or "mp4").strip().lower().lstrip(".") or "mp4"
    rel = Path(kind) / safe_name(name) / f"{stamp}_{uid}.{safe_ext}"
    abs_path = MEDIA_DIR / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(data)
    return f"/media/{rel.as_posix()}", str(abs_path)


def store_bytes(*, data: bytes, kind: str, name: str, ext: str, mime_type: str | None = None) -> tuple[str, str]:
    """优先七牛，失败则本地。返回 (url, key_or_local_path)。"""
    if cdn_enabled():
        key = build_media_key(kind, name, ext)
        # 先写临时文件再上传，避免大文件占内存二次拷贝问题
        tmp = MEDIA_DIR / "staging" / f"{uuid.uuid4().hex}.{ext}"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        try:
            url = upload_local_file(local_path=tmp, key=key, mime_type=mime_type)
            return url, key
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    url, path = save_local_media(data=data, kind=kind, name=name, ext=ext)
    return url, path


def store_local_file(*, local_path: str | Path, kind: str, name: str, ext: str, mime_type: str | None = None) -> tuple[str, str]:
    path = Path(local_path)
    if cdn_enabled():
        key = build_media_key(kind, name, ext)
        url = upload_local_file(local_path=path, key=key, mime_type=mime_type)
        return url, key
    # 复制到 media 目录
    data = path.read_bytes()
    return save_local_media(data=data, kind=kind, name=name, ext=ext)
