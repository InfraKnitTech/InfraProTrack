import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from core.time_utils import now_ist, to_ist_naive
from models.activity_log import ActivityLog
from models.agent import AgentDevice, FileUsage, RawAgentEvent
from models.monitoring import AppRule, IdleLog
from models.usage import AppUsage, BrowserUrlActivity, UrlUsage
from models.user import User
from services.prohibited_alerts import record_prohibited_usage


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

    if event_type in {"app_session_start", "idle_start"}:
        return False

    if event_type == "active_window":
        return _normalize_active_window_sample(db, user, payload, raw.captured_at)

    if event_type == "app_session_end":
        return _normalize_app_session(db, raw.agent_id, user, payload, raw.captured_at)

    if event_type == "idle_end":
        return _normalize_idle(db, user, payload, raw.captured_at)

    if event_type in {"login", "logout"}:
        captured_at = _parse_dt(payload.get("captured_at")) or raw.captured_at or now_ist()
        db.add(ActivityLog(
            user_id=user.id,
            type=event_type,
            start_time=_ist_naive(captured_at),
            end_time=_ist_naive(captured_at),
            duration=0,
        ))
        return True

    if event_type == "file_active":
        return _normalize_file_usage(db, raw.agent_id, user, payload, raw.captured_at)

    if event_type in {"url_active", "url_session_end"}:
        return _normalize_url_usage(db, user, payload, raw.captured_at)

    return False


def _normalize_app_session(db: Session, agent_id: int, user: User, payload: dict[str, Any], fallback_time: datetime | None) -> bool:
    start_time = _parse_dt(payload.get("start_time")) or fallback_time or now_ist()
    end_time = _parse_dt(payload.get("end_time")) or fallback_time or start_time
    duration = _duration(payload, start_time, end_time)
    if duration <= 0:
        return False

    app_name = _clean(payload.get("app_name")) or _clean(payload.get("process_name")) or "Unknown"
    window_title = _clean(payload.get("window_title"))
    file_path = _clean(payload.get("file_path"))
    url = _clean(payload.get("url"))
    category = _classify_app(db, app_name, window_title)
    activity_type = "unproductive" if category in {"unproductive", "prohibited"} else "active"

    if not payload.get("app_usage_already_sampled"):
        db.add(ActivityLog(
            user_id=user.id,
            type=activity_type,
            app_name=app_name,
            window_title=window_title,
            url=url,
            file_path=file_path,
            start_time=_ist_naive(start_time),
            end_time=_ist_naive(end_time),
            duration=duration,
        ))
    if not payload.get("app_usage_already_sampled"):
        _upsert_app_usage(db, user.id, app_name, category, _ist_naive(start_time), duration)

    if file_path:
        db.add(FileUsage(
            agent_id=agent_id,
            user_id=user.id,
            file_path=file_path,
            app_name=app_name,
            window_title=window_title,
            start_time=_ist_naive(start_time),
            end_time=_ist_naive(end_time),
            duration=duration,
        ))
    if category == "prohibited":
        record_prohibited_usage(
            db,
            user=user,
            resource_type="application",
            occurred_at=_ist_naive(end_time),
            duration=duration,
            app_name=app_name,
            window_title=window_title,
        )
    return True


def _normalize_active_window_sample(db: Session, user: User, payload: dict[str, Any], fallback_time: datetime | None) -> bool:
    start_time = _parse_dt(payload.get("start_time")) or fallback_time or now_ist()
    end_time = _parse_dt(payload.get("end_time")) or fallback_time or start_time
    duration = _duration(payload, start_time, end_time)
    if duration <= 0:
        return False

    app_name = _clean(payload.get("app_name")) or _clean(payload.get("process_name")) or "Unknown"
    window_title = _clean(payload.get("window_title"))
    url = _clean(payload.get("url"))
    file_path = _clean(payload.get("file_path"))
    category = _classify_app(db, app_name, window_title)
    activity_type = "unproductive" if category in {"unproductive", "prohibited"} else "active"
    db.add(ActivityLog(
        user_id=user.id,
        type=activity_type,
        app_name=app_name,
        window_title=window_title,
        url=url,
        file_path=file_path,
        start_time=_ist_naive(start_time),
        end_time=_ist_naive(end_time),
        duration=duration,
    ))
    _upsert_app_usage(db, user.id, app_name, category, _ist_naive(start_time), duration)
    return True


def _normalize_idle(db: Session, user: User, payload: dict[str, Any], fallback_time: datetime | None) -> bool:
    start_time = _parse_dt(payload.get("start_time")) or fallback_time or now_ist()
    end_time = _parse_dt(payload.get("end_time")) or fallback_time or start_time
    duration = _duration(payload, start_time, end_time)
    if duration <= 0:
        return False

    db.add(ActivityLog(
        user_id=user.id,
        type="idle",
        start_time=_ist_naive(start_time),
        end_time=_ist_naive(end_time),
        duration=duration,
    ))
    db.add(IdleLog(
        user_id=user.id,
        start_time=_ist_naive(start_time),
        end_time=_ist_naive(end_time),
        duration=duration,
        reason_category=_clean(payload.get("reason_category")),
        reason=_clean(payload.get("reason")),
        project_id=user.project_id,
        manager_id=user.manager_id,
        shift_id=user.shift_id,
    ))
    return True


def _normalize_file_usage(db: Session, agent_id: int, user: User, payload: dict[str, Any], fallback_time: datetime | None) -> bool:
    file_path = _clean(payload.get("file_path"))
    if not file_path:
        return False

    captured_at = _parse_dt(payload.get("captured_at")) or fallback_time or now_ist()
    db.add(FileUsage(
        agent_id=agent_id,
        user_id=user.id,
        file_path=file_path,
        app_name=_clean(payload.get("app_name")),
        window_title=_clean(payload.get("window_title")),
        start_time=_ist_naive(captured_at),
        end_time=_ist_naive(captured_at),
        duration=int(payload.get("duration") or 0),
    ))
    return True


def _normalize_url_usage(db: Session, user: User, payload: dict[str, Any], fallback_time: datetime | None) -> bool:
    url = _clean(payload.get("url"))
    if not url:
        return False

    start_time = _parse_dt(payload.get("start_time")) or fallback_time or now_ist()
    end_time = _parse_dt(payload.get("end_time")) or fallback_time or start_time
    duration = _duration(payload, start_time, end_time)
    if duration <= 0:
        return False
    domain = _clean(payload.get("domain")) or urlparse(url).netloc or url.split("/")[0]
    category = _classify_domain(db, domain, url)
    activity_type = "unproductive" if category in {"unproductive", "prohibited"} else "active"

    if not payload.get("usage_only"):
        db.add(ActivityLog(
            user_id=user.id,
            type=activity_type,
            app_name=_clean(payload.get("app_name")),
            window_title=_clean(payload.get("window_title")),
            url=url,
            start_time=_ist_naive(start_time),
            end_time=_ist_naive(end_time),
            duration=duration,
        ))
    db.add(BrowserUrlActivity(
        user_id=user.id,
        app_name=_clean(payload.get("app_name")),
        process_name=_clean(payload.get("process_name")),
        window_title=_clean(payload.get("window_title")),
        domain=domain,
        url=url,
        category=category,
        start_time=_ist_naive(start_time),
        end_time=_ist_naive(end_time),
        duration=duration,
    ))
    _upsert_url_usage(db, user.id, domain, url, category, _ist_naive(start_time), duration)
    if category == "prohibited":
        record_prohibited_usage(
            db,
            user=user,
            resource_type="domain",
            occurred_at=_ist_naive(end_time),
            duration=duration,
            app_name=_clean(payload.get("app_name")),
            domain=domain,
            url=url,
            window_title=_clean(payload.get("window_title")),
        )
    return True


def _resolve_user(db: Session, agent: AgentDevice, payload: dict[str, Any]) -> User | None:
    if not agent.user_id:
        return None
    return db.query(User).filter(
        User.id == agent.user_id,
        User.is_monitoring_subject.is_(True),
    ).first()


def _classify_app(db: Session, app_name: str, window_title: str | None) -> str:
    terms = [value.lower() for value in (app_name, window_title or "") if value]
    heuristic = _heuristic_category(" ".join(terms))
    if heuristic != "neutral":
        return heuristic
    rules = db.query(AppRule).filter(AppRule.app_name.isnot(None)).all()
    for rule in rules:
        rule_name = (rule.app_name or "").lower()
        if rule_name and any(rule_name in term or term in rule_name for term in terms):
            return rule.category
    return "neutral"


def _classify_domain(db: Session, domain: str, url: str | None) -> str:
    domain_l = (domain or "").lower()
    url_l = (url or "").lower()
    heuristic = _heuristic_category(f"{domain_l} {url_l}")
    if heuristic != "neutral":
        return heuristic
    rules = db.query(AppRule).filter(AppRule.domain.isnot(None)).all()
    for rule in rules:
        rule_domain = (rule.domain or "").lower()
        if rule_domain and (rule_domain in domain_l or rule_domain in url_l):
            return rule.category
    return "neutral"


def _heuristic_category(text: str) -> str:
    value = (text or "").lower()
    educational_terms = (
        "tutorial", "coding", "programming", "developer", "development", "python",
        "javascript", "react", "fastapi", "course", "lecture", "lesson", "learn",
        "training", "education", "explained", "documentation",
    )
    entertainment_terms = (
        "movie", "music", "song", "songs", "trailer", "shorts", "comedy",
        "web series", "episode", "official video", "lyrics",
    )
    gaming_terms = (
        "game", "gaming", "games", "onlinegames", "poki", "crazygames",
        "miniclip", "roblox", "steam", "epicgames", "casino", "betting",
    )
    if "youtube" in value or "youtu.be" in value:
        if any(term in value for term in educational_terms):
            return "productive"
        if any(term in value for term in entertainment_terms):
            return "unproductive"
        return "unproductive"
    if any(term in value for term in gaming_terms):
        return "unproductive"
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
    return max(0, int((_ist_naive(end_time) - _ist_naive(start_time)).total_seconds()))


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ist_naive(value: datetime) -> datetime:
    return to_ist_naive(value) or value


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
