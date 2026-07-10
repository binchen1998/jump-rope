"""中国时区日期工具。"""

from datetime import date, datetime, timedelta, timezone

CHINA_TZ = timezone(timedelta(hours=8))


def now_cn() -> datetime:
    return datetime.now(CHINA_TZ)


def today_cn() -> date:
    return now_cn().date()


def today_cn_str() -> str:
    return today_cn().isoformat()


def china_day_start_utc(d: date | None = None) -> datetime:
    """返回某中国日历日 00:00 对应的 naive UTC（与 datetime.utcnow 存库一致）。"""
    day = d or today_cn()
    local = datetime(day.year, day.month, day.day, tzinfo=CHINA_TZ)
    return local.astimezone(timezone.utc).replace(tzinfo=None)
