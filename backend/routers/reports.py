from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from core.time_utils import IST
from core.deps import get_current_user, get_db
from models.activity_log import ActivityLog
from models.monitoring import IdleLog, ProductivityScore, ProhibitedUsageAlert
from models.project import Project, ProjectTask
from models.shift import Shift
from models.user import User
from schemas.reports import (
    EmployeeProductivityReportResponse,
    EmployeeProductivityReportRow,
    IdleTimeReportResponse,
    IdleTimeReportRow,
    ProhibitedUsageReportResponse,
    ProhibitedUsageReportRow,
    ProductivitySummaryResponse,
    ProductivitySummaryRow,
)
from services.report_excel import build_excel_workbook

router = APIRouter(prefix="/api/reports", tags=["Reports"])

GroupBy = Literal["project", "manager", "shift", "employee"]
EmployeeReportGroupBy = Literal["project", "manager", "shift", "employee"]
ExportTimezone = Literal["Asia/Kolkata", "UTC"]


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
        joinedload(ActivityLog.user),
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
    user_query = db.query(User).options(
        joinedload(User.project),
        joinedload(User.shift),
        joinedload(User.manager),
        joinedload(User.manager_profile),
    ).filter(
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    )

    users = [user for user in user_query.order_by(User.full_name.asc(), User.username.asc()).all() if _can_view_user(current_user, user)]
    users_by_id = {user.id: user for user in users}
    metric_rows = _employee_report_metric_rows(db, list(users_by_id), start_at, end_at)
    score_rows = _employee_productivity_scores(db, list(users_by_id), start_at, end_at)

    rows: list[EmployeeProductivityReportRow] = []
    for user_id, metrics in metric_rows.items():
        user = users_by_id[user_id]
        group_id, group_name = _group_key(db, group_by, user)
        rows.append(EmployeeProductivityReportRow(
            group_by=group_by,
            group_id=group_id,
            group_name=group_name,
            employee_id=user.id,
            employee_name=user.full_name or user.username,
            username=user.username,
            productivity_score=score_rows.get(user.id),
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
        project_id, project_name = _effective_project(db, idle.user)
        manager_id, manager_name = _effective_manager(db, idle.user)
        shift = idle.shift or idle.user.shift
        rows.append(IdleTimeReportRow(
            id=idle.id,
            employee_id=idle.user_id,
            employee_name=idle.user.full_name or idle.user.username,
            username=idle.user.username,
            project_name=idle.project.name if idle.project else project_name,
            manager_name=(idle.manager.full_name or idle.manager.username) if idle.manager else manager_name,
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


@router.get(
    "/prohibited-usage",
    response_model=ProhibitedUsageReportResponse,
    summary="Prohibited application and domain usage alerts",
)
def prohibited_usage_report(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_at, end_at = _date_range(start_date, end_date)
    query = db.query(ProhibitedUsageAlert).options(
        joinedload(ProhibitedUsageAlert.user).joinedload(User.project),
        joinedload(ProhibitedUsageAlert.user).joinedload(User.shift),
        joinedload(ProhibitedUsageAlert.user).joinedload(User.manager),
        joinedload(ProhibitedUsageAlert.project),
        joinedload(ProhibitedUsageAlert.manager),
        joinedload(ProhibitedUsageAlert.shift),
    ).join(User, ProhibitedUsageAlert.user_id == User.id).filter(
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    )
    if start_at:
        query = query.filter(ProhibitedUsageAlert.last_seen_at >= start_at)
    if end_at:
        query = query.filter(ProhibitedUsageAlert.first_seen_at < end_at)

    rows: list[ProhibitedUsageReportRow] = []
    for alert in query.order_by(ProhibitedUsageAlert.last_seen_at.desc(), ProhibitedUsageAlert.id.desc()).all():
        if not _can_view_user(current_user, alert.user):
            continue
        _project_id, fallback_project = _effective_project(db, alert.user)
        _manager_id, fallback_manager = _effective_manager(db, alert.user)
        project = alert.project
        manager = alert.manager
        shift = alert.shift or alert.user.shift
        rows.append(ProhibitedUsageReportRow(
            id=alert.id,
            employee_id=alert.user_id,
            employee_name=alert.user.full_name or alert.user.username,
            username=alert.user.username,
            project_name=project.name if project else fallback_project,
            manager_name=(manager.full_name or manager.username) if manager else fallback_manager,
            shift_name=shift.name if shift else None,
            resource_type=alert.resource_type,
            app_name=alert.app_name,
            domain=alert.domain,
            url=alert.url,
            window_title=alert.window_title,
            first_seen_at=alert.first_seen_at,
            last_seen_at=alert.last_seen_at,
            duration=int(alert.duration or 0),
            occurrence_count=int(alert.occurrence_count or 0),
            manager_email=alert.manager_email,
            email_status=alert.email_status,
            email_error=alert.email_error,
        ))

    return ProhibitedUsageReportResponse(
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        rows=rows,
    )


@router.get(
    "/exports/manager-project-employee.xlsx",
    summary="Export manager, project, and employee productivity workbook",
)
def export_manager_project_employee_productivity(
    start_date: date | None = None,
    end_date: date | None = None,
    report_timezone: ExportTimezone = Query("Asia/Kolkata"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    managers = productivity_summary("manager", start_date, end_date, db, current_user).rows
    projects = productivity_summary("project", start_date, end_date, db, current_user).rows
    employees = employee_productivity_summary("manager", start_date, end_date, db, current_user).rows
    timezone_label = _timezone_label(report_timezone)
    workbook = build_excel_workbook(
        "Manager / Project / Employee Productivity Report",
        [
            (
                "Manager Wise",
                _summary_headers("Manager"),
                [_summary_export_row(row, timezone_label, report_timezone) for row in managers],
            ),
            (
                "Project Wise",
                _summary_headers("Project"),
                [_summary_export_row(row, timezone_label, report_timezone) for row in projects],
            ),
            (
                "Employee Wise",
                ["Manager", "Employee", "Username", f"Login ({timezone_label})", f"Logout ({timezone_label})", "Active", "Productive", "Idle"],
                [_employee_summary_export_row(row, timezone_label, report_timezone) for row in employees],
            ),
        ],
        _export_metadata("Manager / Project / Employee Productivity Report", start_date, end_date, timezone_label),
    )
    return _xlsx_response(workbook, "manager-project-employee-productivity.xlsx")


@router.get(
    "/exports/employee-comprehensive.xlsx",
    summary="Export comprehensive employee productivity workbook",
)
def export_employee_comprehensive_productivity(
    start_date: date | None = None,
    end_date: date | None = None,
    report_timezone: ExportTimezone = Query("Asia/Kolkata"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_at, end_at = _date_range(start_date, end_date)
    timezone_label = _timezone_label(report_timezone)
    rows = _comprehensive_employee_export_rows(db, current_user, start_at, end_at, report_timezone)
    workbook = build_excel_workbook(
        "Employee Comprehensive Productivity Report",
        [
            (
                "Employee Productivity",
                [
                    "Project",
                    "Manager",
                    "Shift",
                    "Employee",
                    "Username",
                    f"Login ({timezone_label})",
                    f"Logout ({timezone_label})",
                    "Active",
                    "Productive",
                    "Unproductive",
                    "Idle",
                    "Tracked",
                    "Productivity %",
                ],
                rows,
            ),
        ],
        _export_metadata("Employee Comprehensive Productivity Report", start_date, end_date, timezone_label),
    )
    return _xlsx_response(workbook, "employee-comprehensive-productivity.xlsx")


@router.get(
    "/exports/timezone-optimized.xlsx",
    summary="Export timezone-optimized productivity workbook",
)
def export_timezone_optimized_productivity(
    start_date: date | None = None,
    end_date: date | None = None,
    report_timezone: ExportTimezone = Query("Asia/Kolkata"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_at, end_at = _date_range(start_date, end_date)
    timezone_label = _timezone_label(report_timezone)
    employee_rows = _comprehensive_employee_export_rows(db, current_user, start_at, end_at, report_timezone)
    idle_rows = _idle_export_rows(db, current_user, start_at, end_at, report_timezone)
    workbook = build_excel_workbook(
        "Timezone Optimized Productivity Report",
        [
            (
                "Employee Productivity",
                [
                    "Project",
                    "Manager",
                    "Shift",
                    "Employee",
                    "Username",
                    f"Login ({timezone_label})",
                    f"Logout ({timezone_label})",
                    "Active",
                    "Productive",
                    "Unproductive",
                    "Idle",
                    "Tracked",
                    "Productivity %",
                ],
                employee_rows,
            ),
            (
                "Idle Breaks",
                [
                    "Employee",
                    "Project",
                    "Manager",
                    "Shift",
                    f"Idle Start ({timezone_label})",
                    f"Idle End ({timezone_label})",
                    "Duration",
                    "Reason Category",
                    "Reason",
                ],
                idle_rows,
            ),
        ],
        _export_metadata("Timezone Optimized Productivity Report", start_date, end_date, timezone_label),
    )
    return _xlsx_response(workbook, f"timezone-optimized-productivity-{report_timezone.replace('/', '-')}.xlsx")


def _summary_headers(group_label: str) -> list[str]:
    return [
        group_label,
        "Employees",
        "Login Events",
        "Logout Events",
        "First Login",
        "Last Logout",
        "Active",
        "Productive",
        "Unproductive",
        "Idle",
        "Tracked",
        "Productivity %",
    ]


def _summary_export_row(row: ProductivitySummaryRow, timezone_label: str, report_timezone: str) -> list:
    return [
        row.group_name,
        row.employee_count,
        row.login_count,
        row.logout_count,
        _format_report_dt(row.first_login, report_timezone),
        _format_report_dt(row.last_logout, report_timezone),
        _duration_hms(row.active_seconds),
        _duration_hms(row.productive_seconds),
        _duration_hms(row.unproductive_seconds),
        _duration_hms(row.idle_seconds),
        _duration_hms(row.total_tracked_seconds),
        row.productivity_percent,
    ]


def _employee_summary_export_row(row: EmployeeProductivityReportRow, timezone_label: str, report_timezone: str) -> list:
    return [
        row.group_name,
        row.employee_name,
        row.username,
        _format_report_dt(row.login_time, report_timezone),
        _format_report_dt(row.logout_time, report_timezone),
        _duration_hms(row.active_seconds),
        _duration_hms(row.productive_seconds),
        _duration_hms(row.idle_seconds),
    ]


def _comprehensive_employee_export_rows(
    db: Session,
    current_user: User,
    start_at: datetime | None,
    end_at: datetime | None,
    report_timezone: str,
) -> list[list]:
    query = db.query(User).options(
        joinedload(User.project),
        joinedload(User.shift),
        joinedload(User.manager),
    ).filter(
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    ).order_by(User.full_name.asc(), User.username.asc())

    rows: list[list] = []
    for user in query.all():
        if not _can_view_user(current_user, user):
            continue
        activities = _employee_activities(db, user.id, start_at, end_at)
        if not activities:
            continue
        metrics = _employee_report_metrics(activities)
        unproductive_seconds = sum(int(activity.duration or 0) for activity in activities if activity.type == "unproductive")
        tracked_seconds = metrics["active_seconds"] + metrics["idle_seconds"]
        productivity_percent = round((metrics["productive_seconds"] / tracked_seconds) * 100, 2) if tracked_seconds else 0.0
        _project_id, project_name = _effective_project(db, user)
        _manager_id, manager_name = _effective_manager(db, user)
        rows.append([
            project_name,
            manager_name,
            user.shift.name if user.shift else "Unassigned Shift",
            user.full_name or user.username,
            user.username,
            _format_report_dt(metrics["login_time"], report_timezone),
            _format_report_dt(metrics["logout_time"], report_timezone),
            _duration_hms(metrics["active_seconds"]),
            _duration_hms(metrics["productive_seconds"]),
            _duration_hms(unproductive_seconds),
            _duration_hms(metrics["idle_seconds"]),
            _duration_hms(tracked_seconds),
            productivity_percent,
        ])
    return rows


def _idle_export_rows(
    db: Session,
    current_user: User,
    start_at: datetime | None,
    end_at: datetime | None,
    report_timezone: str,
) -> list[list]:
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

    rows: list[list] = []
    for idle in query.order_by(IdleLog.start_time.desc(), IdleLog.id.desc()).all():
        if not _can_view_user(current_user, idle.user):
            continue
        _project_id, project_name = _effective_project(db, idle.user)
        _manager_id, manager_name = _effective_manager(db, idle.user)
        project_label = idle.project.name if idle.project else project_name
        manager_label = (idle.manager.full_name or idle.manager.username) if idle.manager else manager_name
        shift = idle.shift or idle.user.shift
        rows.append([
            idle.user.full_name or idle.user.username,
            project_label,
            manager_label,
            shift.name if shift else "Unassigned Shift",
            _format_report_dt(idle.start_time, report_timezone),
            _format_report_dt(idle.end_time, report_timezone),
            _duration_hms(int(idle.duration or 0)),
            idle.reason_category or "Pending",
            idle.reason or "Pending employee reason",
        ])
    return rows


def _xlsx_response(workbook, filename: str) -> StreamingResponse:
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _export_metadata(title: str, start_date: date | None, end_date: date | None, timezone_label: str) -> list[tuple[str, str]]:
    return [
        ("Report", title),
        ("Start date", start_date.isoformat() if start_date else "All available"),
        ("End date", end_date.isoformat() if end_date else "All available"),
        ("Displayed timezone", timezone_label),
        ("Stored source timezone", "Asia/Kolkata (IST)"),
    ]


def _timezone_label(report_timezone: str) -> str:
    return "UTC" if report_timezone == "UTC" else "Asia/Kolkata IST"


def _format_report_dt(value: datetime | None, report_timezone: str) -> str:
    if value is None:
        return "-"
    source = value.replace(tzinfo=IST) if value.tzinfo is None else value.astimezone(IST)
    target = timezone.utc if report_timezone == "UTC" else IST
    converted = source.astimezone(target)
    suffix = "UTC" if report_timezone == "UTC" else "IST"
    return converted.strftime(f"%Y-%m-%d %H:%M:%S {suffix}")


def _duration_hms(seconds: int | None) -> str:
    total_seconds = max(0, int(seconds or 0))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"


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


def _employee_report_metric_rows(
    db: Session,
    user_ids: list[int],
    start_at: datetime | None,
    end_at: datetime | None,
) -> dict[int, dict]:
    if not user_ids:
        return {}

    activity_start = func.coalesce(ActivityLog.start_time, ActivityLog.created_at)
    activity_end = func.coalesce(ActivityLog.end_time, ActivityLog.start_time, ActivityLog.created_at)
    duration = func.coalesce(ActivityLog.duration, 0)
    login_time = func.min(case((ActivityLog.type == "login", activity_start), else_=None))
    logout_time = func.max(case((ActivityLog.type == "logout", activity_start), else_=None))
    first_activity = func.min(activity_start)
    last_session_end = func.max(activity_end)

    query = db.query(
        ActivityLog.user_id.label("user_id"),
        login_time.label("login_time"),
        logout_time.label("logout_time"),
        first_activity.label("first_activity"),
        last_session_end.label("last_session_end"),
        func.sum(case((ActivityLog.type.in_(["active", "unproductive"]), duration), else_=0)).label("active_seconds"),
        func.sum(case((ActivityLog.type == "active", duration), else_=0)).label("productive_seconds"),
        func.sum(case((ActivityLog.type == "idle", duration), else_=0)).label("idle_seconds"),
    ).filter(ActivityLog.user_id.in_(user_ids))
    if start_at:
        query = query.filter(ActivityLog.start_time >= start_at)
    if end_at:
        query = query.filter(ActivityLog.start_time < end_at)

    grouped: dict[int, dict] = {}
    for row in query.group_by(ActivityLog.user_id).all():
        grouped[row.user_id] = {
            "login_time": row.login_time or row.first_activity,
            "logout_time": _max_dt(row.logout_time, row.last_session_end),
            "active_seconds": int(row.active_seconds or 0),
            "productive_seconds": int(row.productive_seconds or 0),
            "idle_seconds": int(row.idle_seconds or 0),
        }
    return grouped


def _employee_productivity_scores(
    db: Session,
    user_ids: list[int],
    start_at: datetime | None,
    end_at: datetime | None,
) -> dict[int, int | None]:
    if not user_ids:
        return {}

    latest_dates_query = db.query(
        ProductivityScore.user_id.label("user_id"),
        func.max(ProductivityScore.date).label("latest_date"),
    ).filter(ProductivityScore.user_id.in_(user_ids))
    if start_at:
        latest_dates_query = latest_dates_query.filter(ProductivityScore.date >= start_at)
    if end_at:
        latest_dates_query = latest_dates_query.filter(ProductivityScore.date < end_at)
    latest_dates = latest_dates_query.group_by(ProductivityScore.user_id).subquery()

    rows = db.query(ProductivityScore.user_id, ProductivityScore.score).join(
        latest_dates,
        (ProductivityScore.user_id == latest_dates.c.user_id)
        & (ProductivityScore.date == latest_dates.c.latest_date),
    ).all()
    return {user_id: int(score) if score is not None else None for user_id, score in rows}




def _group_key(db: Session, group_by: GroupBy, user: User) -> tuple[int | None, str]:
    if group_by == "project":
        return _effective_project(db, user)
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


def _effective_project(db: Session, user: User) -> tuple[int | None, str]:
    if user.project:
        return user.project_id, user.project.name

    managed_project = db.query(Project).filter(Project.manager_id == user.id).order_by(Project.created_at.desc()).first()
    if managed_project:
        return managed_project.id, managed_project.name

    direct_task_project = db.query(Project).join(ProjectTask, ProjectTask.project_id == Project.id).filter(
        ProjectTask.employee_user_id == user.id,
    ).order_by(ProjectTask.created_at.desc()).first()
    if direct_task_project:
        return direct_task_project.id, direct_task_project.name

    manager_task_project = db.query(Project).join(ProjectTask, ProjectTask.project_id == Project.id).filter(
        ProjectTask.manager_user_id == user.id,
    ).order_by(ProjectTask.created_at.desc()).first()
    if manager_task_project:
        return manager_task_project.id, manager_task_project.name

    if user.manager_id:
        team_task_project = db.query(Project).join(ProjectTask, ProjectTask.project_id == Project.id).filter(
            ProjectTask.manager_user_id == user.manager_id,
        ).order_by(ProjectTask.created_at.desc()).first()
        if team_task_project:
            return team_task_project.id, team_task_project.name

    return None, "Unassigned Project"


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
