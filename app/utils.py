from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def ensure_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime, accepting naive values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_db_utc(value: datetime) -> datetime:
    """Store UTC as naive to keep SQLite/Postgres behaviour identical."""
    return ensure_utc(value).replace(tzinfo=None)


def from_db_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return ensure_utc(value)


def local_to_utc(day: date, local_time: time, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    return datetime.combine(day, local_time, tzinfo=tz).astimezone(timezone.utc)


def utc_to_local(value: datetime, tz_name: str) -> datetime:
    return ensure_utc(value).astimezone(ZoneInfo(tz_name))


def day_bounds_utc(day: date, tz_name: str) -> tuple[datetime, datetime]:
    start = local_to_utc(day, time.min, tz_name)
    end = local_to_utc(day + timedelta(days=1), time.min, tz_name)
    return start, end


def format_local(value: datetime, tz_name: str) -> str:
    local = utc_to_local(value, tz_name)
    return local.strftime("%d/%m/%Y %H:%M")


def summarize_slot(start_at: datetime, end_at: datetime, tz_name: str) -> str:
    local_start = utc_to_local(start_at, tz_name)
    local_end = utc_to_local(end_at, tz_name)
    return f"{local_start.strftime('%d/%m/%Y %H:%M')}–{local_end.strftime('%H:%M')}"
