import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from models.activity_log import ActivityLog
from models.agent import AgentDevice, FileUsage, RawAgentEvent
from models.monitoring import AppRule, IdleLog
from models.usage import AppUsage, UrlUsage
from models.user import User


@dataclass
class NormalizationResult:
    normalized: int = 0
    skipped: int = 0


def normalize_pending_events(db: Session, agent_id: int | None = None, limit: int = 500) -> NormalizationResult:
    query = db.query(RawAgentEvent).filter(RawAgentEvent.normalized.is_(False))
    if agent_id is not None:
        query = query.filter(RawAgentEvent.agent_id == agent_id)

    events = query.order_by(RawAgentEvent.id.asc()).limit(limit).all()
    result = NormalizationResult()

    for raw in events:
        payload = _payload(raw)
        user = _resolve_user(db, raw.agent, payload)
        if not user:
            result.skipped += 1
            continue
        created = _normalize_event(db, raw, user, payload)
        raw.normalized = True
        if created:
            result.normalized += 1
        else:
            result.skipped += 1

    return result


def _payload(raw: RawAgentEvent) -> dict[str, Any]:
    try:
        data = json.loads(raw.payload or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_event(db: Session, raw: RawAgentEvent, user: User, payload: dict[str, Any]) -> bool:
    event_type = raw.event_type

    if event_type in {"app_session_start", "active_window", "idle_start"}:
        return False

    if event_type == "app_session_end":
        return _normalize_app_session(db, raw.agent_id, user, payload, raw.captured_at)

    if event_type == "idle_end":
        return _normalize_idle(db, user, payload, raw.captured_at)

    if event_type in {"login", "logout"}:
        captured_at = _parse_dt(payload.get("captured_at")) or raw.captured_at or datetime.utcnow()
        db.add(ActivityLog(
            user_id=user.id,
            type=event_type,
            start_time=_naive_utc(captured_at),
            end_time=_naive_utc(captured_at),
            duration=0,
        ))
        return True

    if event_type == "file_active":
        return _normalize_file_usage(db, raw.agent_id, user, payload, raw.captured_at)

    if event_type in {"url_active", "url_session_end"}:
        return _normalize_url_usage(db, user, payload, raw.captured_at)

    return False


def _normalize_app_session(db: Session, agent_id: int, user: User, payload: dict[str, Any], fallback_time: datetime | None) -> bool:
    start_time = _parse_dt(payload.get("start_time")) or fallback_time or datetime.utcnow()
    end_time = _parse_dt(payload.get("end_time")) or fallback_time or start_time
    duration = _duration(payload, start_time, end_time)
    if duration <= 0:
        return False

    app_name = _clean(payload.get("app_name")) or _clean(payload.get("process_name")) or "Unknown"
    window_title = _clean(payload.get("window_title"))
    file_path = _clean(payload.get("file_path"))
    category = _classify_app(db, app_name, window_title)
    activity_type = "unproductive" if category in {"unproductive", "prohibited"} else "active"

    db.add(ActivityLog(
        user_id=user.id,
        type=activity_type,
        app_name=app_name,
        window_title=window_title,
        file_path=file_path,
        start_time=_naive_utc(start_time),
        end_time=_naive_utc(end_time),
        duration=duration,
    ))
    _upsert_app_usage(db, user.id, app_name, category, _naive_utc(start_time), duration)

    if file_path:
        db.add(FileUsage(
            agent_id=agent_id,
            user_id=user.id,
            file_path=file_path,
            app_name=app_name,
            window_title=window_title,
            start_time=_naive_utc(start_time),
            end_time=_naive_utc(end_time),
            duration=duration,
        ))
    return True


def _normalize_idle(db: Session, user: User, payload: dict[str, Any], fallback_time: datetime | None) -> bool:
    start_time = _parse_dt(payload.get("start_time")) or fallback_time or datetime.utcnow()
    end_time = _parse_dt(payload.get("end_time")) or fallback_time or start_time
    duration = _duration(payload, start_time, end_time)
    if duration <= 0:
        return False

    db.add(ActivityLog(
        user_id=user.id,
        type="idle",
        start_time=_naive_utc(start_time),
        end_time=_naive_utc(end_time),
        duration=duration,
    ))
    db.add(IdleLog(
        user_id=user.id,
        start_time=_naive_utc(start_time),
        duration=duration,
        reason=_clean(payload.get("reason")),
    ))
    return True


def _normalize_file_usage(db: Session, agent_id: int, user: User, payload: dict[str, Any], fallback_time: datetime | None) -> bool:
    file_path = _clean(payload.get("file_path"))
    if not file_path:
        return False

    captured_at = _parse_dt(payload.get("captured_at")) or fallback_time or datetime.utcnow()
    db.add(FileUsage(
        agent_id=agent_id,
        user_id=user.id,
        file_path=file_path,
        app_name=_clean(payload.get("app_name")),
        window_title=_clean(payload.get("window_title")),
        start_time=_naive_utc(captured_at),
        end_time=_naive_utc(captured_at),
        duration=int(payload.get("duration") or 0),
    ))
    return True


def _normalize_url_usage(db: Session, user: User, payload: dict[str, Any], fallback_time: datetime | None) -> bool:
    url = _clean(payload.get("url"))
    if not url:
        return False

    start_time = _parse_dt(payload.get("start_time")) or fallback_time or datetime.utcnow()
    end_time = _parse_dt(payload.get("end_time")) or fallback_time or start_time
    duration = _duration(payload, start_time, end_time)
    domain = urlparse(url).netloc or url.split("/")[0]
    category = _classify_domain(db, domain, url)
    activity_type = "unproductive" if category in {"unproductive", "prohibited"} else "active"

    db.add(ActivityLog(
        user_id=user.id,
        type=activity_type,
        url=url,
        start_time=_naive_utc(start_time),
        end_time=_naive_utc(end_time),
        duration=duration,
    ))
    _upsert_url_usage(db, user.id, domain, url, category, _naive_utc(start_time), duration)
    return True


def _resolve_user(db: Session, agent: AgentDevice, payload: dict[str, Any]) -> User | None:
    if not agent.user_id:
        return None
    return db.query(User).filter(User.id == agent.user_id, User.role == "employee").first()


def _classify_app(db: Session, app_name: str, window_title: str | None) -> str:
    terms = [value.lower() for value in (app_name, window_title or "") if value]
    rules = db.query(AppRule).filter(AppRule.app_name.isnot(None)).all()
    for rule in rules:
        rule_name = (rule.app_name or "").lower()
        if rule_name and any(rule_name in term or term in rule_name for term in terms):
            return rule.category
    return "neutral"


def _classify_domain(db: Session, domain: str, url: str | None) -> str:
    domain_l = (domain or "").lower()
    url_l = (url or "").lower()
    rules = db.query(AppRule).filter(AppRule.domain.isnot(None)).all()
    for rule in rules:
        rule_domain = (rule.domain or "").lower()
        if rule_domain and (rule_domain in domain_l or rule_domain in url_l):
            return rule.category
    return "neutral"


def _upsert_app_usage(db: Session, user_id: int, app_name: str, category: str, start_time: datetime, duration: int) -> None:
    usage = db.query(AppUsage).filter(
        AppUsage.user_id == user_id,
        AppUsage.app_name == app_name,
        AppUsage.category == category,
        AppUsage.date == start_time.date(),
    ).first()
    if usage:
        usage.duration = int(usage.duration or 0) + duration
        return
    db.add(AppUsage(
        user_id=user_id,
        app_name=app_name,
        category=category,
        duration=duration,
        date=start_time.date(),
    ))


def _upsert_url_usage(db: Session, user_id: int, domain: str, url: str, category: str, start_time: datetime, duration: int) -> None:
    usage = db.query(UrlUsage).filter(
        UrlUsage.user_id == user_id,
        UrlUsage.domain == domain,
        UrlUsage.category == category,
        UrlUsage.date == start_time.date(),
    ).first()
    if usage:
        usage.duration = int(usage.duration or 0) + duration
        usage.url = url
        return
    db.add(UrlUsage(
        user_id=user_id,
        domain=domain,
        url=url,
        category=category,
        duration=duration,
        date=start_time.date(),
    ))


def _duration(payload: dict[str, Any], start_time: datetime, end_time: datetime) -> int:
    try:
        duration = int(payload.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration > 0:
        return duration
    return max(0, int((_naive_utc(end_time) - _naive_utc(start_time)).total_seconds()))


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
