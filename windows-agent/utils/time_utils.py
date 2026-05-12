from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def utc_now() -> datetime:
    return datetime.now(IST)


def utc_iso() -> str:
    return utc_now().isoformat()
