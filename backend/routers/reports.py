from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from core.deps import get_current_user, get_db
from models.activity_log import ActivityLog
from models.monitoring import IdleLog
from models.project import Project
from models.shift import Shift
from models.user import User
from schemas.reports import (
    EmployeeProductivityReportResponse,
    EmployeeProductivityReportRow,
    IdleTimeReportResponse,
    IdleTimeReportRow,
    ProductivitySummaryResponse,
    ProductivitySummaryRow,
)

router = APIRouter(prefix="/api/reports", tags=["Reports"])

GroupBy = Literal["project", "manager", "shift", "employee"]
EmployeeReportGroupBy = Literal["project", "manager", "shift"]


@router.get(
    "/productivity-summary",
    response_model=ProductivitySummaryResponse,
    summary="Project, manager, shift, or employee productivity summary",
)
def productivity_summary(
    group_by: GroupBy = Query("project"),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_at, end_at = _date_range(start_date, end_date)
    query = db.query(ActivityLog).options(
        joinedload(ActivityLog.user).joinedload(User.project),
        joinedload(ActivityLog.user).joinedload(User.shift),
        joinedload(ActivityLog.user).joinedload(User.manager),
    ).join(User, ActivityLog.user_id == User.id).filter(
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    )

    if start_at:
        query = query.filter(ActivityLog.start_time >= start_at)
    if end_at:
        query = query.filter(ActivityLog.start_time < end_at)

    activities = [
        activity
        for activity in query.all()
        if _can_view_user(current_user, activity.user)
    ]

    buckets = defaultdict(_empty_bucket)
    for activity in activities:
        group_id, name = _group_key(db, group_by, activity.user)
        bucket = buckets[group_id]
        bucket["name"] = name
        bucket["employees"].add(activity.user_id)

        duration = int(activity.duration or 0)
        if activity.type == "login":
            bucket["login_count"] += 1
            bucket["first_login"] = _min_dt(bucket["first_login"], activity.start_time)
        elif activity.type == "logout":
            bucket["logout_count"] += 1
            bucket["last_logout"] = _max_dt(bucket["last_logout"], activity.start_time)
        elif activity.type == "idle":
            bucket["idle_seconds"] += duration
        elif activity.type == "unproductive":
            bucket["unproductive_seconds"] += duration
        elif activity.type == "active":
            bucket["productive_seconds"] += duration

    rows = [_row(group_by, group_id, bucket) for group_id, bucket in buckets.items()]
    rows.sort(key=lambda item: item.group_name.lower())
    return ProductivitySummaryResponse(
        group_by=group_by,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        rows=rows,
    )


@router.get(
    "/employee-productivity-summary",
    response_model=EmployeeProductivityReportResponse,
    summary="Employee productivity summary grouped by project, manager, or shift",
)
def employee_productivity_summary(
    group_by: EmployeeReportGroupBy = Query("project"),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_at, end_at = _date_range(start_date, end_date)
    query = db.query(User).options(
        joinedload(User.project),
        joinedload(User.shift),
        joinedload(User.manager),
    ).filter(
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    ).order_by(User.full_name.asc(), User.username.asc())

    rows: list[EmployeeProductivityReportRow] = []
    for user in query.all():
        if not _can_view_user(current_user, user):
            continue
        activities = _employee_activities(db, user.id, start_at, end_at)
        if not activities:
            continue
        group_id, group_name = _group_key(db, group_by, user)
        metrics = _employee_report_metrics(activities)
        rows.append(EmployeeProductivityReportRow(
            group_by=group_by,
            group_id=group_id,
            group_name=group_name,
            employee_id=user.id,
            employee_name=user.full_name or user.username,
            username=user.username,
            **metrics,
        ))

    rows.sort(key=lambda item: (item.group_name.lower(), item.employee_name.lower()))
    return EmployeeProductivityReportResponse(
        group_by=group_by,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        rows=rows,
    )


@router.get(
    "/idle-time",
    response_model=IdleTimeReportResponse,
    summary="Idle time breaks with employee-submitted reasons",
)
def idle_time_report(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_at, end_at = _date_range(start_date, end_date)
    query = db.query(IdleLog).options(
        joinedload(IdleLog.user).joinedload(User.project),
        joinedload(IdleLog.user).joinedload(User.shift),
        joinedload(IdleLog.user).joinedload(User.manager),
        joinedload(IdleLog.project),
        joinedload(IdleLog.manager),
        joinedload(IdleLog.shift),
    ).join(User, IdleLog.user_id == User.id).filter(
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    )
    if start_at:
        query = query.filter(IdleLog.start_time >= start_at)
    if end_at:
        query = query.filter(IdleLog.start_time < end_at)

    rows: list[IdleTimeReportRow] = []
    for idle in query.order_by(IdleLog.start_time.desc(), IdleLog.id.desc()).all():
        if not _can_view_user(current_user, idle.user):
            continue
        project = idle.project or idle.user.project
        manager = idle.manager or idle.user.manager
        shift = idle.shift or idle.user.shift
        rows.append(IdleTimeReportRow(
            id=idle.id,
            employee_id=idle.user_id,
            employee_name=idle.user.full_name or idle.user.username,
            username=idle.user.username,
            project_name=project.name if project else None,
            manager_name=(manager.full_name or manager.username) if manager else None,
            shift_name=shift.name if shift else None,
            start_time=idle.start_time,
            end_time=idle.end_time,
            duration=int(idle.duration or 0),
            reason_category=idle.reason_category,
            reason=idle.reason,
        ))

    return IdleTimeReportResponse(
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        rows=rows,
    )


def _date_range(start_date: date | None, end_date: date | None) -> tuple[datetime | None, datetime | None]:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before or equal to end_date")
    start_at = datetime.combine(start_date, time.min) if start_date else None
    end_at = datetime.combine(end_date + timedelta(days=1), time.min) if end_date else None
    return start_at, end_at


def _can_view_user(current_user: User, target: User) -> bool:
    if not target.is_monitoring_subject or not target.is_active:
        return False
    if current_user.role == "admin":
        return True
    if current_user.role == "manager":
        return target.manager_id == current_user.id or (
            target.project is not None and target.project.manager_id == current_user.id
        )
    return target.id == current_user.id


def _employee_activities(
    db: Session,
    user_id: int,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[ActivityLog]:
    query = db.query(ActivityLog).filter(ActivityLog.user_id == user_id)
    if start_at:
        query = query.filter(ActivityLog.start_time >= start_at)
    if end_at:
        query = query.filter(ActivityLog.start_time < end_at)
    return query.order_by(ActivityLog.start_time.asc(), ActivityLog.id.asc()).all()


def _group_key(db: Session, group_by: GroupBy, user: User) -> tuple[int | None, str]:
    if group_by == "project":
        project: Project | None = user.project
        return user.project_id, project.name if project else "Unassigned Project"
    if group_by == "manager":
        manager_id, manager_name = _effective_manager(db, user)
        return manager_id, manager_name
    if group_by == "shift":
        shift: Shift | None = user.shift
        return user.shift_id, shift.name if shift else "Unassigned Shift"
    return user.id, user.full_name or user.username


def _effective_manager(db: Session, user: User) -> tuple[int | None, str]:
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


def _employee_report_metrics(activities: list[ActivityLog]) -> dict:
    login_time: datetime | None = None
    logout_time: datetime | None = None
    first_activity: datetime | None = None
    last_session_end: datetime | None = None
    active_seconds = 0
    productive_seconds = 0
    idle_seconds = 0

    for activity in activities:
        start_time = activity.start_time or activity.created_at
        end_time = activity.end_time or activity.start_time or activity.created_at
        first_activity = _min_dt(first_activity, start_time)
        last_session_end = _max_dt(last_session_end, end_time)

        duration = int(activity.duration or 0)
        if activity.type == "login":
            login_time = _min_dt(login_time, start_time)
        elif activity.type == "logout":
            logout_time = _max_dt(logout_time, start_time)
        elif activity.type == "idle":
            idle_seconds += duration
        elif activity.type == "active":
            active_seconds += duration
            productive_seconds += duration
        elif activity.type == "unproductive":
            active_seconds += duration

    return {
        "login_time": login_time or first_activity,
        "logout_time": _max_dt(logout_time, last_session_end),
        "active_seconds": active_seconds,
        "productive_seconds": productive_seconds,
        "idle_seconds": idle_seconds,
    }


def _empty_bucket() -> dict:
    return {
        "name": "",
        "employees": set(),
        "login_count": 0,
        "logout_count": 0,
        "first_login": None,
        "last_logout": None,
        "productive_seconds": 0,
        "unproductive_seconds": 0,
        "idle_seconds": 0,
    }


def _row(group_by: str, group_id: int | None, bucket: dict) -> ProductivitySummaryRow:
    productive = bucket["productive_seconds"]
    unproductive = bucket["unproductive_seconds"]
    idle = bucket["idle_seconds"]
    active = productive + unproductive
    total = active + idle
    productivity_percent = round((productive / total) * 100, 2) if total else 0.0
    return ProductivitySummaryRow(
        group_by=group_by,
        group_id=group_id,
        group_name=bucket["name"],
        employee_count=len(bucket["employees"]),
        login_count=bucket["login_count"],
        logout_count=bucket["logout_count"],
        first_login=bucket["first_login"],
        last_logout=bucket["last_logout"],
        productive_seconds=productive,
        unproductive_seconds=unproductive,
        active_seconds=active,
        idle_seconds=idle,
        total_tracked_seconds=total,
        productivity_percent=productivity_percent,
    )


def _min_dt(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if not candidate:
        return current
    return candidate if current is None or candidate < current else current


def _max_dt(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if not candidate:
        return current
    return candidate if current is None or candidate > current else current
