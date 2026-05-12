from collections import defaultdict
from datetime import date, datetime, time, timedelta
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from core.deps import get_current_user, get_db
from models.agent import AgentDevice, RawAgentEvent
from models.monitoring import AppRule
from models.usage import AppUsage, BrowserUrlActivity, UrlUsage
from models.user import User
from schemas.analytics import (
    ActivityDetailResponse,
    ActivityDetailRow,
    ActivityRollupResponse,
    ActivityRollupRow,
    AnalyticsListResponse,
    AnalyticsPoint,
    AppUsageScopeResponse,
    AppUsageScopeRow,
    SessionEventResponse,
    SessionEventRow,
)
from models.activity_log import ActivityLog

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get(
    "/app-usage-scope",
    response_model=AppUsageScopeResponse,
    summary="Top app by overall, agent, employee, manager, or project scope",
)
def app_usage_scope(
    group_by: str = Query("overall", pattern="^(overall|agent|employee|manager|project)$"),
    limit: int = Query(20, ge=1, le=100),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_at, end_at = _date_range(start_date, end_date)
    if group_by == "agent":
        items = _agent_scope_rows(db, current_user, start_at, end_at, limit)
    else:
        items = _normalized_scope_rows(db, current_user, group_by, start_at, end_at, limit)
    return AppUsageScopeResponse(
        group_by=group_by,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        items=items,
    )


@router.get("/top-apps", response_model=AnalyticsListResponse, summary="Top applications across visible users")
def top_apps(
    limit: int = Query(10, ge=1, le=50),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_at, end_at = _date_range(start_date, end_date)
    query = db.query(AppUsage).options(joinedload(AppUsage.user).joinedload(User.project))
    if start_at:
        query = query.filter(AppUsage.date >= start_at.date())
    if end_at:
        query = query.filter(AppUsage.date < end_at.date())

    totals: dict[tuple[str, str | None], int] = defaultdict(int)
    for row in query.all():
        if not _can_view_user(current_user, row.user):
            continue
        category = _classify_app_detail(db, row.app_name, None)
        key = (row.app_name, category if category != "neutral" else row.category)
        totals[key] += int(row.duration or 0)

    items = [
        AnalyticsPoint(name=name, category=category, value=value)
        for (name, category), value in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]
    return AnalyticsListResponse(
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        items=items,
    )


@router.get("/top-domains", response_model=AnalyticsListResponse, summary="Top domains across visible users")
def top_domains(
    limit: int = Query(10, ge=1, le=50),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_at, end_at = _date_range(start_date, end_date)
    query = db.query(UrlUsage).options(joinedload(UrlUsage.user).joinedload(User.project))
    if start_at:
        query = query.filter(UrlUsage.date >= start_at.date())
    if end_at:
        query = query.filter(UrlUsage.date < end_at.date())

    totals: dict[tuple[str, str | None], int] = defaultdict(int)
    for row in query.all():
        if not _can_view_user(current_user, row.user):
            continue
        key = (row.domain, _classify_url_detail(row.domain, row.url, None, row.category))
        totals[key] += int(row.duration or 0)

    items = [
        AnalyticsPoint(name=name, category=category, value=value)
        for (name, category), value in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]
    return AnalyticsListResponse(
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        items=items,
    )


@router.get("/session-events", response_model=SessionEventResponse, summary="Recent login and logout events")
def session_events(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ActivityLog).options(
        joinedload(ActivityLog.user).joinedload(User.project),
    ).join(User, ActivityLog.user_id == User.id).filter(
        ActivityLog.type.in_(["login", "logout"]),
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    ).order_by(ActivityLog.start_time.desc(), ActivityLog.id.desc())

    rows: list[SessionEventRow] = []
    for activity in query.limit(limit * 3).all():
        if not _can_view_user(current_user, activity.user):
            continue
        rows.append(SessionEventRow(
            id=activity.id,
            employee_id=activity.user_id,
            employee_name=activity.user.full_name or activity.user.username,
            username=activity.user.username,
            event_type=activity.type,
            captured_at=activity.start_time,
            department=activity.user.department,
            project_name=activity.user.project.name if activity.user.project else None,
        ))
        if len(rows) >= limit:
            break
    return SessionEventResponse(items=rows)


@router.get("/application-activity", response_model=ActivityDetailResponse, summary="Detailed app activity sessions")
def application_activity(
    limit: int = Query(100, ge=1, le=500),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_at, end_at = _date_range(start_date, end_date)
    start_at = start_at or datetime.combine(date.today(), time.min)
    query = db.query(RawAgentEvent).options(joinedload(RawAgentEvent.agent)).filter(
        RawAgentEvent.event_type == "active_window",
    )
    if start_at:
        query = query.filter(RawAgentEvent.captured_at >= start_at)
    if end_at:
        query = query.filter(RawAgentEvent.captured_at < end_at)
    query = query.order_by(RawAgentEvent.captured_at.desc(), RawAgentEvent.id.desc()).limit(limit * 30)

    rows: list[ActivityDetailRow] = []
    for raw in reversed(query.all()):
        payload = _safe_payload(raw.payload)
        resolved_user = _visible_user_for_agent(db, raw.agent, payload)
        if resolved_user is None or not _can_view_user(current_user, resolved_user):
            continue
        row = _raw_application_detail_row(db, raw, resolved_user, payload)
        if row:
            rows.append(row)
    rows.extend(_idle_detail_rows(db, current_user, start_at, end_at))
    return ActivityDetailResponse(items=_merge_detail_rows(rows, "application")[:limit])


@router.get("/browser-activity", response_model=ActivityDetailResponse, summary="Detailed browser URL activity sessions")
def browser_activity(
    limit: int = Query(100, ge=1, le=500),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_at, end_at = _date_range(start_date, end_date)
    start_at = start_at or datetime.combine(date.today(), time.min)
    query = db.query(BrowserUrlActivity).options(
        joinedload(BrowserUrlActivity.user).joinedload(User.manager),
        joinedload(BrowserUrlActivity.user).joinedload(User.project),
    ).join(User, BrowserUrlActivity.user_id == User.id).filter(
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    )
    if start_at:
        query = query.filter(BrowserUrlActivity.start_time >= start_at)
    if end_at:
        query = query.filter(BrowserUrlActivity.start_time < end_at)
    query = query.order_by(BrowserUrlActivity.start_time.desc(), BrowserUrlActivity.id.desc()).limit(limit * 12)

    rows: list[ActivityDetailRow] = []
    for activity in query.all():
        if not _can_view_user(current_user, activity.user):
            continue
        rows.append(_browser_detail_row(activity))
    return ActivityDetailResponse(items=_merge_detail_rows(rows, "browser")[:limit])


@router.get("/activity-rollup", response_model=ActivityRollupResponse, summary="Productivity rollup by employee, manager, department, or project")
def activity_rollup(
    group_by: str = Query("employee", pattern="^(employee|manager|department|project)$"),
    source: str = Query("application", pattern="^(application|browser|all)$"),
    limit: int = Query(50, ge=1, le=200),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_at, end_at = _date_range(start_date, end_date)
    start_at = start_at or datetime.combine(date.today(), time.min)
    buckets: dict[tuple[int | None, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))

    if source in {"application", "all"}:
        query = db.query(RawAgentEvent).options(joinedload(RawAgentEvent.agent)).filter(
            RawAgentEvent.event_type == "active_window",
        )
        if start_at:
            query = query.filter(RawAgentEvent.captured_at >= start_at)
        if end_at:
            query = query.filter(RawAgentEvent.captured_at < end_at)
        app_rows: list[ActivityDetailRow] = []
        for raw in query.all():
            payload = _safe_payload(raw.payload)
            resolved_user = _visible_user_for_agent(db, raw.agent, payload)
            if resolved_user is None or not _can_view_user(current_user, resolved_user):
                continue
            detail = _raw_application_detail_row(db, raw, resolved_user, payload)
            if detail:
                app_rows.append(detail)
        for detail in _merge_detail_rows(app_rows, "application", newest_first=False):
            user = db.query(User).options(joinedload(User.manager), joinedload(User.project)).filter(User.id == detail.employee_id).first()
            if not user:
                continue
            key = _rollup_group_key(db, group_by, user)
            buckets[key][_analytics_category(detail.category)] += int(detail.duration or 0)

        idle_query = db.query(ActivityLog).options(
            joinedload(ActivityLog.user).joinedload(User.manager),
            joinedload(ActivityLog.user).joinedload(User.project),
        ).join(User, ActivityLog.user_id == User.id).filter(
            ActivityLog.type == "idle",
            User.is_monitoring_subject.is_(True),
            User.is_active.is_(True),
        )
        if start_at:
            idle_query = idle_query.filter(ActivityLog.start_time >= start_at)
        if end_at:
            idle_query = idle_query.filter(ActivityLog.start_time < end_at)
        for row in idle_query.all():
            if not _can_view_user(current_user, row.user):
                continue
            key = _rollup_group_key(db, group_by, row.user)
            buckets[key]["idle"] += int(row.duration or 0)

    if source in {"browser", "all"}:
        query = db.query(BrowserUrlActivity).options(
            joinedload(BrowserUrlActivity.user).joinedload(User.manager),
            joinedload(BrowserUrlActivity.user).joinedload(User.project),
        ).join(User, BrowserUrlActivity.user_id == User.id).filter(
            User.is_monitoring_subject.is_(True),
            User.is_active.is_(True),
        )
        if start_at:
            query = query.filter(BrowserUrlActivity.start_time >= start_at)
        if end_at:
            query = query.filter(BrowserUrlActivity.start_time < end_at)
        for row in query.all():
            if not _can_view_user(current_user, row.user):
                continue
            key = _rollup_group_key(db, group_by, row.user)
            category = _classify_url_detail(row.domain, row.url, row.window_title, row.category)
            buckets[key][_analytics_category(category)] += int(row.duration or 0)

    items = [_rollup_response_row(group_by, key, values) for key, values in buckets.items()]
    items.sort(key=lambda row: row.total_seconds, reverse=True)
    return ActivityRollupResponse(group_by=group_by, source=source, items=items[:limit])


def _date_range(start_date: date | None, end_date: date | None) -> tuple[datetime | None, datetime | None]:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before or equal to end_date")
    start_at = datetime.combine(start_date, time.min) if start_date else None
    end_at = datetime.combine(end_date + timedelta(days=1), time.min) if end_date else None
    return start_at, end_at


def _can_view_user(current_user: User, target: User | None) -> bool:
    if target is None:
        return False
    if not target.is_monitoring_subject or not target.is_active:
        return False
    if current_user.role == "admin":
        return True
    if current_user.role == "manager":
        return target.manager_id == current_user.id or (
            target.project is not None and target.project.manager_id == current_user.id
        )
    return target.id == current_user.id


def _application_detail_row(activity: ActivityLog) -> ActivityDetailRow:
    user = activity.user
    return ActivityDetailRow(
        id=activity.id,
        source="application",
        employee_id=user.id,
        employee_name=user.full_name or user.username,
        username=user.username,
        manager_name=(user.manager.full_name or user.manager.username) if user.manager else None,
        department=user.department,
        project_name=user.project.name if user.project else None,
        application=activity.app_name or ("No active application" if activity.type == "idle" else None),
        window_title=activity.window_title or ("Ideal / no active input" if activity.type == "idle" else None),
        category="ideal" if activity.type == "idle" else ("unproductive" if activity.type == "unproductive" else "productive"),
        start_time=activity.start_time,
        end_time=activity.end_time,
        duration=int(activity.duration or 0),
    )


def _raw_application_detail_row(db: Session, raw: RawAgentEvent, user: User, payload: dict) -> ActivityDetailRow | None:
    start_time = _parse_payload_dt(payload.get("start_time")) or raw.captured_at
    end_time = _parse_payload_dt(payload.get("end_time")) or raw.captured_at or start_time
    duration = _payload_duration(payload)
    if duration <= 0 and start_time and end_time:
        duration = max(0, int((end_time - start_time).total_seconds()))
    if duration <= 0:
        return None
    app_name = str(payload.get("app_name") or payload.get("process_name") or "Unknown").strip() or "Unknown"
    window_title = str(payload.get("window_title") or "").strip() or None
    category = _analytics_category(_classify_app_detail(db, app_name, window_title))
    return ActivityDetailRow(
        id=raw.id,
        source="application",
        employee_id=user.id,
        employee_name=user.full_name or user.username,
        username=user.username,
        manager_name=(user.manager.full_name or user.manager.username) if user.manager else None,
        department=user.department,
        project_name=user.project.name if user.project else None,
        application=app_name,
        window_title=window_title,
        category=category,
        start_time=start_time,
        end_time=end_time,
        duration=duration,
    )


def _browser_detail_row(activity: BrowserUrlActivity) -> ActivityDetailRow:
    user = activity.user
    category = _analytics_category(_classify_url_detail(activity.domain, activity.url, activity.window_title, activity.category))
    return ActivityDetailRow(
        id=activity.id,
        source="browser",
        employee_id=user.id,
        employee_name=user.full_name or user.username,
        username=user.username,
        manager_name=(user.manager.full_name or user.manager.username) if user.manager else None,
        department=user.department,
        project_name=user.project.name if user.project else None,
        application=activity.app_name,
        browser=activity.app_name or activity.process_name,
        domain=activity.domain,
        url=activity.url,
        window_title=activity.window_title,
        category=category,
        start_time=activity.start_time,
        end_time=activity.end_time,
        duration=int(activity.duration or 0),
    )


def _merge_detail_rows(rows: list[ActivityDetailRow], source: str, newest_first: bool = True) -> list[ActivityDetailRow]:
    sorted_rows = sorted(rows, key=lambda row: (row.employee_id, row.start_time or datetime.min, row.id))
    merged: list[ActivityDetailRow] = []
    for row in sorted_rows:
        if not row.start_time or not row.end_time:
            continue
        previous = merged[-1] if merged else None
        if previous and _can_merge_detail_row(previous, row, source):
            previous.end_time = max(previous.end_time or row.end_time, row.end_time)
            previous.duration = int(previous.duration or 0) + int(row.duration or 0)
            previous.window_title = row.window_title or previous.window_title
            continue
        merged.append(row.model_copy())
    if newest_first:
        merged.sort(key=lambda row: row.start_time or datetime.min, reverse=True)
    return merged


def _idle_detail_rows(
    db: Session,
    current_user: User,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[ActivityDetailRow]:
    query = db.query(ActivityLog).options(
        joinedload(ActivityLog.user).joinedload(User.manager),
        joinedload(ActivityLog.user).joinedload(User.project),
    ).join(User, ActivityLog.user_id == User.id).filter(
        ActivityLog.type == "idle",
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    )
    if start_at:
        query = query.filter(ActivityLog.start_time >= start_at)
    if end_at:
        query = query.filter(ActivityLog.start_time < end_at)
    return [
        _application_detail_row(activity)
        for activity in query.all()
        if _can_view_user(current_user, activity.user)
    ]


def _can_merge_detail_row(previous: ActivityDetailRow, current: ActivityDetailRow, source: str) -> bool:
    if previous.employee_id != current.employee_id:
        return False
    if previous.category != current.category:
        return False
    if source == "browser":
        same_target = (
            previous.browser == current.browser
            and previous.domain == current.domain
            and previous.url == current.url
        )
    elif previous.category == "ideal" or current.category == "ideal":
        same_target = previous.category == current.category
    else:
        same_target = previous.application == current.application
    if not same_target or not previous.end_time or not current.start_time:
        return False
    gap = (current.start_time - previous.end_time).total_seconds()
    return gap <= 20


def _analytics_category(category: str | None) -> str:
    if category == "idle" or category == "ideal":
        return "ideal"
    if category in {"unproductive", "prohibited"}:
        return "unproductive"
    return "productive"


def _classify_app_detail(db: Session, app_name: str, window_title: str | None) -> str:
    text = f"{app_name or ''} {window_title or ''}".lower()
    heuristic = _heuristic_category(text)
    if heuristic != "neutral":
        return heuristic
    rules = db.query(AppRule).filter(AppRule.app_name.isnot(None)).all()
    for rule in rules:
        rule_name = (rule.app_name or "").lower()
        if rule_name and rule_name in text:
            return rule.category
    return "productive"


def _classify_url_detail(domain: str | None, url: str | None, window_title: str | None, fallback: str | None) -> str:
    heuristic = _heuristic_category(f"{domain or ''} {url or ''} {window_title or ''}")
    if heuristic != "neutral":
        return heuristic
    return _analytics_category(fallback)


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


def _rollup_group_key(db: Session, group_by: str, user: User) -> tuple[int | None, str]:
    if group_by == "employee":
        return user.id, user.full_name or user.username
    if group_by == "manager":
        return _effective_manager_key(db, user)
    if group_by == "department":
        return None, user.department or "Unassigned Department"
    if group_by == "project":
        return user.project_id, user.project.name if user.project else "Unassigned Project"
    raise HTTPException(status_code=400, detail="Unsupported group_by value")


def _rollup_response_row(group_by: str, key: tuple[int | None, str], values: dict[str, int]) -> ActivityRollupRow:
    productive = int(values.get("productive", 0))
    unproductive = int(values.get("unproductive", 0))
    idle = int(values.get("idle", 0)) + int(values.get("ideal", 0))
    total = productive + unproductive + idle
    return ActivityRollupRow(
        group_by=group_by,
        group_id=key[0],
        group_name=key[1],
        productive_seconds=productive,
        unproductive_seconds=unproductive,
        idle_seconds=idle,
        total_seconds=total,
        productivity_percent=round((productive / total) * 100, 2) if total else 0.0,
    )


def _normalized_scope_rows(
    db: Session,
    current_user: User,
    group_by: str,
    start_at: datetime | None,
    end_at: datetime | None,
    limit: int,
) -> list[AppUsageScopeRow]:
    query = db.query(AppUsage).options(
        joinedload(AppUsage.user).joinedload(User.project),
        joinedload(AppUsage.user).joinedload(User.manager),
    )
    if start_at:
        query = query.filter(AppUsage.date >= start_at.date())
    if end_at:
        query = query.filter(AppUsage.date < end_at.date())

    grouped: dict[tuple[int | None, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals: dict[tuple[int | None, str], int] = defaultdict(int)

    for row in query.all():
        if not _can_view_user(current_user, row.user):
            continue
        group_id, group_name = _usage_group_key(db, group_by, row.user)
        key = (group_id, group_name)
        grouped[key][row.app_name] += int(row.duration or 0)
        totals[key] += int(row.duration or 0)

    return _scope_rows_from_grouped(group_by, grouped, totals, limit)


def _agent_scope_rows(
    db: Session,
    current_user: User,
    start_at: datetime | None,
    end_at: datetime | None,
    limit: int,
) -> list[AppUsageScopeRow]:
    query = db.query(RawAgentEvent).options(joinedload(RawAgentEvent.agent))
    query = query.filter(RawAgentEvent.event_type == "app_session_end")
    if start_at:
        query = query.filter(RawAgentEvent.captured_at >= start_at)
    if end_at:
        query = query.filter(RawAgentEvent.captured_at < end_at)

    grouped: dict[tuple[int | None, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals: dict[tuple[int | None, str], int] = defaultdict(int)

    for row in query.all():
        payload = _safe_payload(row.payload)
        resolved_user = _visible_user_for_agent(db, row.agent, payload)
        if resolved_user is None or not _can_view_user(current_user, resolved_user):
            continue

        app_name = str(payload.get("app_name") or payload.get("process_name") or "Unknown").strip() or "Unknown"
        duration = _payload_duration(payload)
        agent_name = _agent_group_name(row.agent)
        key = (row.agent_id, agent_name)
        grouped[key][app_name] += duration
        totals[key] += duration

    return _scope_rows_from_grouped("agent", grouped, totals, limit)


def _scope_rows_from_grouped(
    group_by: str,
    grouped: dict[tuple[int | None, str], dict[str, int]],
    totals: dict[tuple[int | None, str], int],
    limit: int,
) -> list[AppUsageScopeRow]:
    rows: list[AppUsageScopeRow] = []
    for (group_id, group_name), app_map in grouped.items():
        sorted_apps = sorted(app_map.items(), key=lambda item: item[1], reverse=True)
        top_app_name, top_app_seconds = sorted_apps[0] if sorted_apps else (None, 0)
        rows.append(AppUsageScopeRow(
            group_by=group_by,
            group_id=group_id,
            group_name=group_name,
            total_seconds=totals[(group_id, group_name)],
            top_app_name=top_app_name,
            top_app_seconds=top_app_seconds,
            distinct_app_count=len(app_map),
        ))
    rows.sort(key=lambda row: row.total_seconds, reverse=True)
    return rows[:limit]


def _usage_group_key(db: Session, group_by: str, user: User) -> tuple[int | None, str]:
    if group_by == "overall":
        return None, "All Visible Agents"
    if group_by == "employee":
        return user.id, user.full_name or user.username
    if group_by == "manager":
        return _effective_manager_key(db, user)
    if group_by == "project":
        project = user.project
        return user.project_id, project.name if project else "Unassigned Project"
    raise HTTPException(status_code=400, detail="Unsupported group_by value")


def _effective_manager_key(db: Session, user: User) -> tuple[int | None, str]:
    if user.manager:
        return user.manager_id, user.manager.full_name or user.manager.username
    if user.role == "manager" or user.manager_profile:
        return user.id, user.full_name or user.username
    has_reports = db.query(User.id).filter(
        User.manager_id == user.id,
        User.is_active.is_(True),
        User.is_monitoring_subject.is_(True),
    ).first()
    if has_reports:
        return user.id, user.full_name or user.username
    manages_project = db.query(Project.id).filter(Project.manager_id == user.id).first()
    if manages_project:
        return user.id, user.full_name or user.username
    return None, "Unassigned Manager"


def _safe_payload(payload_text: str) -> dict:
    try:
        payload = json.loads(payload_text or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _payload_duration(payload: dict) -> int:
    try:
        return max(0, int(payload.get("duration") or 0))
    except (TypeError, ValueError):
        return 0


def _parse_payload_dt(value) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError:
        return None


def _agent_group_name(agent: AgentDevice | None) -> str:
    if agent is None:
        return "Unknown Agent"
    username = (agent.username or "").strip()
    hostname = (agent.hostname or "").strip()
    if username and hostname:
        return f"{hostname} ({username})"
    return hostname or username or f"Agent {agent.id}"


def _visible_user_for_agent(db: Session, agent: AgentDevice | None, payload: dict) -> User | None:
    if agent is None or not agent.user_id:
        return None
    return db.query(User).filter(
        User.id == agent.user_id,
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    ).first()
