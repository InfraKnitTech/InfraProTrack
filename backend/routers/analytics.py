from collections import defaultdict
from datetime import date, datetime, time, timedelta
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from core.deps import get_current_user, get_db
from models.agent import AgentDevice, RawAgentEvent
from models.usage import AppUsage, UrlUsage
from models.user import User
from schemas.analytics import (
    AnalyticsListResponse,
    AnalyticsPoint,
    AppUsageScopeResponse,
    AppUsageScopeRow,
)

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
        key = (row.app_name, row.category)
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
        key = (row.domain, row.category)
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
        group_id, group_name = _usage_group_key(group_by, row.user)
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


def _usage_group_key(group_by: str, user: User) -> tuple[int | None, str]:
    if group_by == "overall":
        return None, "All Visible Agents"
    if group_by == "employee":
        return user.id, user.full_name or user.username
    if group_by == "manager":
        manager = user.manager
        return user.manager_id, (manager.full_name or manager.username) if manager else "Unassigned Manager"
    if group_by == "project":
        project = user.project
        return user.project_id, project.name if project else "Unassigned Project"
    raise HTTPException(status_code=400, detail="Unsupported group_by value")


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
