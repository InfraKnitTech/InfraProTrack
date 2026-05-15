from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload, load_only, selectinload

from core.deps import get_db, require_role
from core.security import get_password_hash
from models.agent import AgentDevice
from models.activity_log import ActivityLog
from models.employee import EmployeeAsset, EmployeeHistory
from models.project import Project
from models.shift import EmployeeShiftAssignment, Shift
from models.usage import AppUsage, BrowserUrlActivity
from models.user import User
from schemas.employees import (
    EmployeeCreate,
    EmployeeHistoryOut,
    EmployeeHistoryResponse,
    EmployeeInsightEvent,
    EmployeeInsightResponse,
    EmployeeListResponse,
    EmployeeOut,
    PendingEmployeeAgentListResponse,
    PendingEmployeeAgentOut,
    EmployeeUpdate,
)

router = APIRouter(prefix="/api/employees", tags=["Employees"])


@router.get("", response_model=EmployeeListResponse, summary="List organization employees")
def list_employees(
    status_filter: str | None = Query(default=None, alias="status"),
    name: str | None = None,
    department: str | None = None,
    designation: str | None = None,
    project_id: int | None = None,
    shift_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    query = _employee_query(db, include_detail=False)
    if status_filter:
        query = query.filter(User.employment_status == status_filter)
    if name:
        like = f"%{name.strip()}%"
        query = query.filter((User.full_name.ilike(like)) | (User.username.ilike(like)) | (User.email.ilike(like)))
    if department:
        query = query.filter(User.department == department)
    if designation:
        query = query.filter(User.designation == designation)
    if project_id:
        query = query.filter(User.project_id == project_id)
    if shift_id:
        query = query.filter(User.shift_id == shift_id)
    rows = [user for user in query.order_by(User.full_name.asc(), User.username.asc()).all() if _can_view_employee(current_user, user)]
    return EmployeeListResponse(items=[_employee_out(user, include_detail=False) for user in rows])


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED, summary="Create an employee")
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    _validate_unique_employee(db, payload.username, payload.email, payload.employee_code)
    _validate_refs(db, current_user, payload.manager_id, payload.project_id, payload.shift_id)
    agent = _load_unlinked_agent(db, payload.agent_id) if payload.agent_id else None
    user = User(
        username=payload.username.strip(),
        full_name=payload.full_name.strip(),
        email=payload.email,
        password=get_password_hash(payload.password or "Employee@123"),
        role="employee",
        employee_code=_clean(payload.employee_code),
        department=_clean(payload.department),
        phone=_clean(payload.phone),
        location=_clean(payload.location),
        designation=_clean(payload.designation),
        employment_status=payload.employment_status,
        is_active=payload.employment_status == "working",
        is_monitoring_subject=True,
        manager_id=payload.manager_id,
        project_id=payload.project_id,
        shift_id=payload.shift_id,
        created_by_id=current_user.id,
    )
    db.add(user)
    db.flush()
    if agent:
        agent.user_id = user.id
        _add_history(
            db,
            user.id,
            "agent_linked",
            "agent_id",
            None,
            f"{agent.hostname} ({agent.device_id})",
            current_user.id,
        )
    _replace_assets(db, user.id, payload.assets)
    _replace_schedule(db, user.id, payload.schedule)
    _add_history(db, user.id, "created", None, None, "Employee created", current_user.id)
    db.commit()
    return _employee_out(_load_employee(db, user.id))


@router.get("/pending-agents", response_model=PendingEmployeeAgentListResponse, summary="List registered agents waiting for employee confirmation")
def pending_employee_agents(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin", "manager")),
):
    agents = db.query(AgentDevice).filter(
        AgentDevice.is_active.is_(True),
        AgentDevice.user_id.is_(None),
    ).options(
        load_only(
            AgentDevice.id,
            AgentDevice.device_id,
            AgentDevice.hostname,
            AgentDevice.username,
            AgentDevice.os_type,
            AgentDevice.os_version,
            AgentDevice.agent_version,
            AgentDevice.ip_address,
            AgentDevice.status,
            AgentDevice.last_seen_at,
            AgentDevice.registered_at,
        )
    ).order_by(AgentDevice.last_seen_at.desc(), AgentDevice.registered_at.desc()).all()
    return PendingEmployeeAgentListResponse(items=[_pending_agent_out(db, agent) for agent in agents])


@router.get("/{employee_id}", response_model=EmployeeOut, summary="Get employee details")
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    user = _load_employee(db, employee_id)
    if not user or not _can_view_employee(current_user, user):
        raise HTTPException(status_code=404, detail="Employee not found")
    return _employee_out(user)


@router.put("/{employee_id}", response_model=EmployeeOut, summary="Update employee details")
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    user = _load_employee(db, employee_id)
    if not user or not _can_view_employee(current_user, user):
        raise HTTPException(status_code=404, detail="Employee not found")
    _validate_unique_employee(db, payload.username, payload.email, payload.employee_code, exclude_id=user.id)
    _validate_refs(db, current_user, payload.manager_id, payload.project_id, payload.shift_id)
    before = _snapshot_employee(user)
    before_assets = _assets_summary(user.assets)
    before_schedule = _schedule_summary(user.shift_assignments)

    user.username = payload.username.strip()
    user.full_name = payload.full_name.strip()
    user.email = payload.email
    if payload.password:
        user.password = get_password_hash(payload.password)
    user.employee_code = _clean(payload.employee_code)
    user.department = _clean(payload.department)
    user.phone = _clean(payload.phone)
    user.location = _clean(payload.location)
    user.designation = _clean(payload.designation)
    user.employment_status = payload.employment_status
    user.is_active = payload.employment_status == "working"
    user.manager_id = payload.manager_id
    user.project_id = payload.project_id
    user.shift_id = payload.shift_id

    _replace_assets(db, user.id, payload.assets)
    _replace_schedule(db, user.id, payload.schedule)
    db.flush()
    db.expire(user, ["assets", "shift_assignments"])
    db.refresh(user)
    _record_field_history(db, user.id, before, _snapshot_employee(user), current_user.id)
    _record_summary_history(db, user.id, "assets", before_assets, _assets_summary(user.assets), current_user.id)
    _record_summary_history(db, user.id, "schedule", before_schedule, _schedule_summary(user.shift_assignments), current_user.id)
    db.commit()
    return _employee_out(_load_employee(db, user.id))


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Mark employee as left organization")
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    user = _load_employee(db, employee_id)
    if not user or not _can_view_employee(current_user, user):
        raise HTTPException(status_code=404, detail="Employee not found")
    old_status = user.employment_status
    user.employment_status = "left"
    user.is_active = False
    _add_history(db, user.id, "status_changed", "employment_status", old_status, "left", current_user.id)
    db.commit()


@router.get("/{employee_id}/insights", response_model=EmployeeInsightResponse, summary="Employee activity insight")
def employee_insights(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    user = _load_employee(db, employee_id)
    if not user or not _can_view_employee(current_user, user):
        raise HTTPException(status_code=404, detail="Employee not found")

    activities = db.query(ActivityLog).filter(ActivityLog.user_id == employee_id).order_by(ActivityLog.start_time.desc()).all()
    browser_activities = db.query(BrowserUrlActivity).filter(
        BrowserUrlActivity.user_id == employee_id,
    ).order_by(BrowserUrlActivity.start_time.desc()).limit(400).all()
    productive = sum(int(row.duration or 0) for row in activities if row.type == "active")
    unproductive = sum(int(row.duration or 0) for row in activities if row.type == "unproductive")
    idle = sum(int(row.duration or 0) for row in activities if row.type == "idle")
    total = productive + unproductive + idle

    app_totals: dict[str, int] = defaultdict(int)
    for row in db.query(AppUsage).filter(AppUsage.user_id == employee_id).all():
        app_totals[row.app_name] += int(row.duration or 0)

    return EmployeeInsightResponse(
        employee=_employee_out(user),
        productive_seconds=productive,
        unproductive_seconds=unproductive,
        idle_seconds=idle,
        total_tracked_seconds=total,
        productivity_percent=round((productive / total) * 100, 2) if total else 0.0,
        top_apps=[
            {"name": name, "value": value}
            for name, value in sorted(app_totals.items(), key=lambda item: item[1], reverse=True)[:10]
        ],
        recent_activity=_recent_activity_rows(activities[:400], browser_activities)[:50],
        history=_history_rows(user.history),
    )


@router.get("/{employee_id}/history", response_model=EmployeeHistoryResponse, summary="Employee change history")
def employee_history(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    user = _load_employee(db, employee_id)
    if not user or not _can_view_employee(current_user, user):
        raise HTTPException(status_code=404, detail="Employee not found")
    return EmployeeHistoryResponse(items=_history_rows(user.history))


def _employee_query(db: Session, include_detail: bool = True):
    options = [
        joinedload(User.manager),
        joinedload(User.project),
        joinedload(User.shift),
        joinedload(User.created_by),
    ]
    if include_detail:
        options.extend([
            selectinload(User.assets),
            selectinload(User.shift_assignments).joinedload(EmployeeShiftAssignment.shift),
            selectinload(User.history).joinedload(EmployeeHistory.changed_by),
        ])
    return db.query(User).options(*options).filter(User.is_monitoring_subject.is_(True))


def _load_employee(db: Session, employee_id: int) -> User | None:
    return _employee_query(db).filter(User.id == employee_id).first()


def _employee_out(user: User, include_detail: bool = True) -> EmployeeOut:
    assets = list(user.assets or []) if include_detail else []
    assignments = list(user.shift_assignments or []) if include_detail else []
    return EmployeeOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name or user.username,
        email=user.email,
        role=user.role,
        employee_code=user.employee_code,
        department=user.department,
        phone=user.phone,
        location=user.location,
        designation=user.designation,
        employment_status=user.employment_status or "working",
        is_active=bool(user.is_active),
        manager_id=user.manager_id,
        manager_name=(user.manager.full_name or user.manager.username) if user.manager else None,
        project_id=user.project_id,
        project_name=user.project.name if user.project else None,
        shift_id=user.shift_id,
        shift_name=user.shift.name if user.shift else None,
        created_at=user.created_at,
        created_by_id=user.created_by_id,
        created_by_name=(user.created_by.full_name or user.created_by.username) if user.created_by else None,
        assets=assets,
        schedule=[
            {
                "id": item.id,
                "weekday": item.weekday,
                "shift_id": item.shift_id,
                "shift_name": item.shift.name,
                "start_time": item.shift.start_time.isoformat(),
                "end_time": item.shift.end_time.isoformat(),
                "timezone": item.shift.timezone,
            }
            for item in sorted(assignments, key=lambda row: row.weekday)
            if item.shift
        ],
    )


def _replace_assets(db: Session, user_id: int, assets: list) -> None:
    db.query(EmployeeAsset).filter(EmployeeAsset.user_id == user_id).delete()
    for asset in assets:
        db.add(EmployeeAsset(
            user_id=user_id,
            asset_type=_clean(asset.asset_type),
            asset_name=asset.asset_name.strip(),
            asset_tag=_clean(asset.asset_tag),
            notes=_clean(asset.notes),
        ))


def _replace_schedule(db: Session, user_id: int, schedule: list) -> None:
    db.query(EmployeeShiftAssignment).filter(EmployeeShiftAssignment.user_id == user_id).delete()
    seen_weekdays: set[int] = set()
    for item in schedule:
        if item.weekday in seen_weekdays:
            raise HTTPException(status_code=400, detail="Each weekday can have only one assigned shift")
        seen_weekdays.add(item.weekday)
        if not db.query(Shift).filter(Shift.id == item.shift_id).first():
            raise HTTPException(status_code=400, detail=f"Invalid shift_id: {item.shift_id}")
        db.add(EmployeeShiftAssignment(user_id=user_id, weekday=item.weekday, shift_id=item.shift_id))


def _validate_unique_employee(
    db: Session,
    username: str,
    email: str,
    employee_code: str | None,
    exclude_id: int | None = None,
) -> None:
    query = db.query(User).filter(User.username == username)
    if exclude_id:
        query = query.filter(User.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=400, detail="Username already exists")
    query = db.query(User).filter(User.email == email)
    if exclude_id:
        query = query.filter(User.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=400, detail="Email already exists")
    if employee_code:
        query = db.query(User).filter(User.employee_code == employee_code)
        if exclude_id:
            query = query.filter(User.id != exclude_id)
        if query.first():
            raise HTTPException(status_code=400, detail="Employee code already exists")


def _validate_refs(db: Session, current_user: User, manager_id: int | None, project_id: int | None, shift_id: int | None) -> None:
    if manager_id and not db.query(User).filter(
        User.id == manager_id,
        User.is_active.is_(True),
        User.is_monitoring_subject.is_(True),
    ).first():
        raise HTTPException(status_code=400, detail="Manager/leader employee not found")
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or (current_user.role == "manager" and project.manager_id != current_user.id):
            raise HTTPException(status_code=400, detail="Project not found")
    if shift_id and not db.query(Shift).filter(Shift.id == shift_id).first():
        raise HTTPException(status_code=400, detail="Shift not found")


def _load_unlinked_agent(db: Session, agent_id: int | None) -> AgentDevice:
    agent = db.query(AgentDevice).filter(AgentDevice.id == agent_id, AgentDevice.is_active.is_(True)).first()
    if not agent:
        raise HTTPException(status_code=400, detail="Agent not found")
    if agent.user_id:
        raise HTTPException(status_code=400, detail="Agent is already linked to an employee")
    return agent


def _pending_agent_out(db: Session, agent: AgentDevice) -> PendingEmployeeAgentOut:
    display_name = _clean(agent.hostname) or _clean(agent.username) or f"Agent {agent.id}"
    username = _unique_username(db, _safe_identifier(agent.username or agent.hostname or f"agent-{agent.id}"))
    return PendingEmployeeAgentOut(
        agent_id=agent.id,
        device_id=agent.device_id,
        hostname=agent.hostname,
        username=agent.username,
        os_type=agent.os_type,
        os_version=agent.os_version,
        agent_version=agent.agent_version,
        ip_address=agent.ip_address,
        status=agent.status,
        last_seen_at=agent.last_seen_at,
        registered_at=agent.registered_at,
        suggested_full_name=display_name,
        suggested_username=username,
        suggested_email=_unique_email(db, f"{username}@agents.infraprotrack.com"),
        suggested_employee_code=_unique_employee_code(db, f"AGENT-{agent.device_id[:24]}"),
    )


def _safe_identifier(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "." for ch in value.strip())
    cleaned = ".".join(part for part in cleaned.split(".") if part)
    return (cleaned or "agent.employee")[:90]


def _unique_username(db: Session, base: str) -> str:
    candidate = base
    index = 2
    while db.query(User.id).filter(User.username == candidate).first():
        candidate = f"{base[:85]}.{index}"
        index += 1
    return candidate


def _unique_email(db: Session, base: str) -> str:
    local, domain = base.split("@", 1)
    candidate = base
    index = 2
    while db.query(User.id).filter(User.email == candidate).first():
        candidate = f"{local[:80]}.{index}@{domain}"
        index += 1
    return candidate


def _unique_employee_code(db: Session, base: str) -> str:
    candidate = base
    index = 2
    while db.query(User.id).filter(User.employee_code == candidate).first():
        candidate = f"{base[:55]}-{index}"
        index += 1
    return candidate


def _can_view_employee(current_user: User, target: User) -> bool:
    if current_user.role == "admin":
        return True
    return target.manager_id == current_user.id


def _recent_activity_rows(activities: list[ActivityLog], browser_activities: list[BrowserUrlActivity]) -> list[EmployeeInsightEvent]:
    rows: list[EmployeeInsightEvent] = [
        EmployeeInsightEvent(
            id=row.id,
            type=row.type,
            app_name=row.app_name,
            window_title=row.window_title,
            url=row.url,
            domain=None,
            start_time=row.start_time,
            end_time=row.end_time,
            duration=int(row.duration or 0),
        )
        for row in activities
        if not row.url
    ]
    for row in browser_activities:
        rows.append(EmployeeInsightEvent(
            id=row.id,
            type="unproductive" if row.category in {"unproductive", "prohibited"} else "active",
            app_name=row.app_name or row.process_name,
            window_title=row.window_title,
            url=row.url,
            domain=row.domain,
            start_time=row.start_time,
            end_time=row.end_time,
            duration=int(row.duration or 0),
        ))
    return _merge_activity_events(rows)[:50]


def _merge_activity_events(rows: list[EmployeeInsightEvent]) -> list[EmployeeInsightEvent]:
    sorted_rows = sorted(rows, key=lambda item: item.start_time or item.end_time or datetime.min)
    merged: list[EmployeeInsightEvent] = []
    for row in sorted_rows:
        previous = merged[-1] if merged else None
        if previous and _can_merge_activity_event(previous, row):
            previous.end_time = max(previous.end_time or row.end_time, row.end_time or previous.end_time)
            previous.duration = int(previous.duration or 0) + int(row.duration or 0)
            previous.window_title = row.window_title or previous.window_title
            previous.url = row.url or previous.url
            previous.domain = row.domain or previous.domain
            continue
        merged.append(row)
    return sorted(merged, key=lambda item: item.start_time or item.end_time or datetime.min, reverse=True)


def _can_merge_activity_event(previous: EmployeeInsightEvent, current: EmployeeInsightEvent) -> bool:
    if previous.type != current.type:
        return False
    if (previous.app_name or "") != (current.app_name or ""):
        return False
    previous_target = previous.url or previous.window_title or ""
    current_target = current.url or current.window_title or ""
    if previous_target != current_target:
        return False
    if not previous.end_time or not current.start_time:
        return False
    return (current.start_time - previous.end_time).total_seconds() <= 20


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _snapshot_employee(user: User) -> dict[str, str | None]:
    return {
        "full_name": user.full_name,
        "email": user.email,
        "employee_code": user.employee_code,
        "department": user.department,
        "phone": user.phone,
        "location": user.location,
        "designation": user.designation,
        "employment_status": user.employment_status,
        "manager_id": str(user.manager_id) if user.manager_id else None,
        "project_id": str(user.project_id) if user.project_id else None,
        "shift_id": str(user.shift_id) if user.shift_id else None,
    }


def _record_field_history(db: Session, user_id: int, before: dict, after: dict, changed_by_id: int | None) -> None:
    for field_name, old_value in before.items():
        new_value = after.get(field_name)
        if old_value != new_value:
            _add_history(db, user_id, "field_changed", field_name, old_value, new_value, changed_by_id)


def _record_summary_history(db: Session, user_id: int, field_name: str, old_value: str, new_value: str, changed_by_id: int | None) -> None:
    if old_value != new_value:
        _add_history(db, user_id, f"{field_name}_changed", field_name, old_value, new_value, changed_by_id)


def _add_history(
    db: Session,
    user_id: int,
    change_type: str,
    field_name: str | None,
    old_value: str | None,
    new_value: str | None,
    changed_by_id: int | None,
) -> None:
    db.add(EmployeeHistory(
        user_id=user_id,
        change_type=change_type,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        changed_by_id=changed_by_id,
    ))


def _assets_summary(assets) -> str:
    rows = [
        f"{asset.asset_name} ({asset.asset_tag or asset.asset_type or 'asset'})"
        for asset in sorted(assets or [], key=lambda item: item.id or 0)
    ]
    return "; ".join(rows)


def _schedule_summary(assignments) -> str:
    rows = [
        f"{item.weekday}:{item.shift.name if item.shift else item.shift_id}"
        for item in sorted(assignments or [], key=lambda row: row.weekday)
    ]
    return "; ".join(rows)


def _history_rows(history) -> list[EmployeeHistoryOut]:
    return [
        EmployeeHistoryOut(
            id=row.id,
            change_type=row.change_type,
            field_name=row.field_name,
            old_value=row.old_value,
            new_value=row.new_value,
            changed_by_id=row.changed_by_id,
            changed_by_name=(row.changed_by.full_name or row.changed_by.username) if row.changed_by else None,
            created_at=row.created_at,
        )
        for row in sorted(history or [], key=lambda item: item.created_at, reverse=True)
    ]
