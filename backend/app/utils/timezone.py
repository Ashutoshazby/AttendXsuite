from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return now_utc()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def local_date_key(value: datetime | None = None, tz: str = "Asia/Kolkata") -> str:
    local = (value or now_utc()).astimezone(ZoneInfo(tz))
    return local.strftime("%Y-%m-%d")


def day_range_utc(date_key: str | None = None, tz: str = "Asia/Kolkata") -> tuple[datetime, datetime]:
    zone = ZoneInfo(tz)
    if date_key:
      year, month, day = [int(part) for part in date_key.split("-")]
      start_local = datetime.combine(datetime(year, month, day), time.min, zone)
    else:
      local_now = now_utc().astimezone(zone)
      start_local = datetime.combine(local_now.date(), time.min, zone)
    end_local = start_local + timedelta(days=1) - timedelta(milliseconds=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
