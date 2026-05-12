from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from core.deps import get_db, require_role
from models.activity_log import ActivityLog
from models.groups import CustomGroup, CustomGroupMember
from models.project import Project, ProjectTask
from models.user import User
from schemas.projects import (
    ProjectCreate,
    ProjectDashboardResponse,
    ProjectDashboardRow,
    ProjectListResponse,
    ProjectResponse,
    ProjectSummaryResponse,
    ProjectTaskCreate,
    ProjectTaskResponse,
    ProjectTaskUpdate,
    ProjectUpdate,
)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


@router.get("", response_model=ProjectListResponse, summary="List projects with live productivity rollups")
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    projects = db.query(Project).options(
        joinedload(Project.manager),
        joinedload(Project.tasks),
    ).order_by(Project.created_at.desc(), Project.name.asc()).all()
    return ProjectListResponse(
        items=[_to_project_response(db, project) for project in projects if _can_view_project(current_user, project)]
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, summary="Create a project")
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    manager_id = _validated_user_id(db, payload.manager_id) if payload.manager_id else None
    project = Project(
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        client_name=(payload.client_name or "").strip() or None,
        status=payload.status,
        manager_id=manager_id,
    )
    db.add(project)
    db.commit()
    stored = _load_project(db, project.id)
    return _to_project_response(db, stored)


@router.put("/{project_id}", response_model=ProjectResponse, summary="Update a project")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    project = _load_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if payload.name is not None:
        project.name = payload.name.strip()
    if "description" in payload.model_fields_set:
        project.description = (payload.description or "").strip() or None
    if "client_name" in payload.model_fields_set:
        project.client_name = (payload.client_name or "").strip() or None
    if payload.status is not None:
        project.status = payload.status
    if "manager_id" in payload.model_fields_set:
        project.manager_id = _validated_user_id(db, payload.manager_id) if payload.manager_id else None
    db.commit()
    stored = _load_project(db, project.id)
    return _to_project_response(db, stored)


@router.get("/{project_id}/dashboard", response_model=ProjectDashboardResponse, summary="Project and manager drilldown dashboard")
def project_dashboard(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    project = _load_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not _can_view_project(current_user, project):
        raise HTTPException(status_code=403, detail="Not allowed to view this project")

    employees = _project_employees(db, project.id)
    activities = db.query(ActivityLog).filter(ActivityLog.user_id.in_([user.id for user in employees])).all() if employees else []
    return ProjectDashboardResponse(
        project=_to_project_response(db, project),
        tasks=[_to_task_response(task) for task in sorted(project.tasks, key=lambda item: item.created_at, reverse=True)],
        manager_rows=_rollup_by_manager(db, project, employees, activities),
        employee_rows=_rollup_by_employee(employees, activities),
    )


@router.post("/{project_id}/tasks", response_model=ProjectTaskResponse, status_code=status.HTTP_201_CREATED, summary="Assign a project task")
def create_project_task(
    project_id: int,
    payload: ProjectTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    project = _load_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not _can_manage_project(current_user, project):
        raise HTTPException(status_code=403, detail="Not allowed to assign tasks for this project")
    assignee = _validated_assignee(db, payload.assignee_type, payload.group_id, payload.manager_user_id, payload.employee_user_id)
    task = ProjectTask(
        project_id=project.id,
        title=payload.title.strip(),
        description=(payload.description or "").strip() or None,
        assignee_type=payload.assignee_type,
        group_id=assignee["group_id"],
        manager_user_id=assignee["manager_user_id"],
        employee_user_id=assignee["employee_user_id"],
        due_at=payload.due_at,
        status=payload.status,
        created_by=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _to_task_response(task)


@router.put("/{project_id}/tasks/{task_id}", response_model=ProjectTaskResponse, summary="Update a project task")
def update_project_task(
    project_id: int,
    task_id: int,
    payload: ProjectTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    project = _load_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not _can_manage_project(current_user, project):
        raise HTTPException(status_code=403, detail="Not allowed to update tasks for this project")
    task = db.query(ProjectTask).filter(ProjectTask.id == task_id, ProjectTask.project_id == project_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if payload.title is not None:
        task.title = payload.title.strip()
    if "description" in payload.model_fields_set:
        task.description = (payload.description or "").strip() or None
    if payload.status is not None:
        task.status = payload.status
    if "due_at" in payload.model_fields_set:
        task.due_at = payload.due_at
    if payload.assignee_type is not None:
        assignee = _validated_assignee(db, payload.assignee_type, payload.group_id, payload.manager_user_id, payload.employee_user_id)
        task.assignee_type = payload.assignee_type
        task.group_id = assignee["group_id"]
        task.manager_user_id = assignee["manager_user_id"]
        task.employee_user_id = assignee["employee_user_id"]
    db.commit()
    db.refresh(task)
    return _to_task_response(task)


def _load_project(db: Session, project_id: int) -> Project | None:
    return db.query(Project).options(
        joinedload(Project.manager),
        joinedload(Project.tasks).joinedload(ProjectTask.group),
        joinedload(Project.tasks).joinedload(ProjectTask.manager_user),
        joinedload(Project.tasks).joinedload(ProjectTask.employee_user),
    ).filter(Project.id == project_id).first()


def _validated_user_id(db: Session, user_id: int | None) -> int | None:
    if user_id is None:
        return None
    user = db.query(User).filter(
        User.id == user_id,
        User.is_active.is_(True),
        User.is_monitoring_subject.is_(True),
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid employee or manager")
    return user.id


def _validated_assignee(
    db: Session,
    assignee_type: str,
    group_id: int | None,
    manager_user_id: int | None,
    employee_user_id: int | None,
) -> dict[str, int | None]:
    assignee = {"group_id": None, "manager_user_id": None, "employee_user_id": None}
    if assignee_type == "group":
        group = db.query(CustomGroup).filter(CustomGroup.id == group_id).first()
        if not group:
            raise HTTPException(status_code=400, detail="Invalid group assignee")
        assignee["group_id"] = group.id
    elif assignee_type == "manager":
        assignee["manager_user_id"] = _validated_user_id(db, manager_user_id)
    elif assignee_type == "employee":
        assignee["employee_user_id"] = _validated_user_id(db, employee_user_id)
    else:
        raise HTTPException(status_code=400, detail="Unsupported assignee type")
    return assignee


def _project_employees(db: Session, project_id: int) -> list[User]:
    user_ids = _project_user_ids(db, project_id)
    if not user_ids:
        return []
    return db.query(User).filter(
        User.id.in_(user_ids),
        User.is_active.is_(True),
        User.is_monitoring_subject.is_(True),
    ).order_by(User.full_name.asc(), User.username.asc()).all()


def _project_user_ids(db: Session, project_id: int, visited_projects: set[int] | None = None) -> set[int]:
    visited_projects = visited_projects or set()
    if project_id in visited_projects:
        return set()
    visited_projects.add(project_id)

    project = _load_project(db, project_id)
    if not project:
        return set()

    user_ids: set[int] = set()
    direct_members = db.query(User.id).filter(
        User.project_id == project_id,
        User.is_active.is_(True),
        User.is_monitoring_subject.is_(True),
    ).all()
    user_ids.update(row[0] for row in direct_members)

    if project.manager_id:
        user_ids.update(_manager_scope_user_ids(db, project.manager_id))

    for task in project.tasks:
        if task.employee_user_id:
            user_ids.add(task.employee_user_id)
        if task.manager_user_id:
            user_ids.update(_manager_scope_user_ids(db, task.manager_user_id))
        if task.group_id:
            user_ids.update(_group_scope_user_ids(db, task.group_id, visited_groups=set(), visited_projects=visited_projects))

    return user_ids


def _manager_scope_user_ids(db: Session, manager_id: int) -> set[int]:
    ids = {manager_id}
    rows = db.query(User.id).filter(
        User.manager_id == manager_id,
        User.is_active.is_(True),
        User.is_monitoring_subject.is_(True),
    ).all()
    ids.update(row[0] for row in rows)
    return ids


def _group_scope_user_ids(
    db: Session,
    group_id: int,
    visited_groups: set[int],
    visited_projects: set[int],
) -> set[int]:
    if group_id in visited_groups:
        return set()
    visited_groups.add(group_id)

    ids: set[int] = set()
    group = db.query(CustomGroup).options(
        joinedload(CustomGroup.members),
        joinedload(CustomGroup.child_groups),
    ).filter(CustomGroup.id == group_id).first()
    if not group:
        return ids

    for member in group.members:
        ids.update(_group_member_user_ids(db, member, visited_groups, visited_projects))
    for child in group.child_groups:
        ids.update(_group_scope_user_ids(db, child.id, visited_groups, visited_projects))
    return ids


def _group_member_user_ids(
    db: Session,
    member: CustomGroupMember,
    visited_groups: set[int],
    visited_projects: set[int],
) -> set[int]:
    if member.member_type == "user":
        return {member.user_id} if member.user_id else set()
    if member.member_type == "manager":
        return _manager_scope_user_ids(db, member.manager_user_id) if member.manager_user_id else set()
    if member.member_type == "project":
        return _project_user_ids(db, member.project_id, visited_projects) if member.project_id else set()
    if member.member_type == "department" and member.department_name:
        rows = db.query(User.id).filter(
            User.department == member.department_name,
            User.is_active.is_(True),
            User.is_monitoring_subject.is_(True),
        ).all()
        return {row[0] for row in rows}
    return set()


def _project_summary(db: Session, project: Project) -> ProjectSummaryResponse:
    employees = _project_employees(db, project.id)
    user_ids = [user.id for user in employees]
    activities = db.query(ActivityLog).filter(ActivityLog.user_id.in_(user_ids)).all() if user_ids else []
    metrics = _activity_metrics(activities)
    open_tasks = sum(1 for task in project.tasks if task.status != "completed")
    return ProjectSummaryResponse(
        employee_count=len(user_ids),
        task_count=len(project.tasks),
        open_task_count=open_tasks,
        **metrics,
    )


def _activity_metrics(activities: list[ActivityLog]) -> dict:
    productive = sum(int(item.duration or 0) for item in activities if item.type == "active")
    unproductive = sum(int(item.duration or 0) for item in activities if item.type == "unproductive")
    idle = sum(int(item.duration or 0) for item in activities if item.type == "idle")
    active = productive + unproductive
    total = active + idle
    return {
        "productive_seconds": productive,
        "unproductive_seconds": unproductive,
        "active_seconds": active,
        "idle_seconds": idle,
        "total_tracked_seconds": total,
        "productivity_percent": round((productive / total) * 100, 2) if total else 0.0,
    }


def _rollup_by_manager(db: Session, project: Project, employees: list[User], activities: list[ActivityLog]) -> list[ProjectDashboardRow]:
    users_by_manager: dict[int | None, list[User]] = defaultdict(list)
    activities_by_user: dict[int, list[ActivityLog]] = defaultdict(list)
    employee_lookup = {user.id: user for user in employees}
    for user in employees:
        users_by_manager[_effective_manager_id(db, user, project.manager_id)].append(user)
    for activity in activities:
        activities_by_user[activity.user_id].append(activity)

    rows: list[ProjectDashboardRow] = []
    for manager_id, manager_employees in users_by_manager.items():
        manager = employee_lookup.get(manager_id)
        if not manager and manager_id:
            manager = db.query(User).filter(User.id == manager_id).first()
        row_activities = []
        for user in manager_employees:
            row_activities.extend(activities_by_user.get(user.id, []))
        rows.append(ProjectDashboardRow(
            id=manager_id,
            name=(manager.full_name or manager.username) if manager else "Unassigned manager",
            employee_count=len(manager_employees),
            **_activity_metrics(row_activities),
        ))
    return sorted(rows, key=lambda row: row.name)


def _effective_manager_id(db: Session, user: User, project_manager_id: int | None = None) -> int | None:
    if user.manager_id:
        return user.manager_id
    if project_manager_id:
        return project_manager_id
    if user.role == "manager":
        return user.id
    has_reports = db.query(User.id).filter(
        User.manager_id == user.id,
        User.is_active.is_(True),
        User.is_monitoring_subject.is_(True),
    ).first()
    if has_reports:
        return user.id
    manages_project = db.query(Project.id).filter(Project.manager_id == user.id).first()
    if manages_project:
        return user.id
    return None


def _rollup_by_employee(employees: list[User], activities: list[ActivityLog]) -> list[ProjectDashboardRow]:
    activities_by_user: dict[int, list[ActivityLog]] = defaultdict(list)
    for activity in activities:
        activities_by_user[activity.user_id].append(activity)
    return [
        ProjectDashboardRow(
            id=user.id,
            name=user.full_name or user.username,
            employee_count=1,
            **_activity_metrics(activities_by_user.get(user.id, [])),
        )
        for user in employees
    ]


def _to_project_response(db: Session, project: Project) -> ProjectResponse:
    manager = project.manager
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        client_name=project.client_name,
        status=project.status,
        manager_id=project.manager_id,
        manager_name=(manager.full_name or manager.username) if manager else None,
        created_at=project.created_at,
        summary=_project_summary(db, project),
    )


def _to_task_response(task: ProjectTask) -> ProjectTaskResponse:
    assignee_label = "-"
    if task.assignee_type == "group" and task.group:
        assignee_label = task.group.name
    elif task.assignee_type == "manager" and task.manager_user:
        assignee_label = task.manager_user.full_name or task.manager_user.username
    elif task.assignee_type == "employee" and task.employee_user:
        assignee_label = task.employee_user.full_name or task.employee_user.username
    return ProjectTaskResponse(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        assignee_type=task.assignee_type,
        assignee_label=assignee_label,
        group_id=task.group_id,
        manager_user_id=task.manager_user_id,
        employee_user_id=task.employee_user_id,
        due_at=task.due_at,
        status=task.status,
        created_by=task.created_by,
        created_at=task.created_at,
    )


def _can_view_project(current_user: User, project: Project) -> bool:
    if current_user.role == "admin":
        return True
    return project.manager_id == current_user.id


def _can_manage_project(current_user: User, project: Project) -> bool:
    if current_user.role == "admin":
        return True
    return project.manager_id == current_user.id
