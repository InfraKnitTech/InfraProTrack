from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from core.deps import get_db, require_role
from models.activity_log import ActivityLog
from models.groups import CustomGroup, CustomGroupMember
from models.project import Project
from models.user import User
from schemas.groups import (
    GroupCreate,
    GroupListResponse,
    GroupMemberResponse,
    GroupOption,
    GroupOptionsResponse,
    GroupResponse,
    GroupSummaryResponse,
    GroupUpdate,
)

router = APIRouter(prefix="/api/groups", tags=["Groups"])


@router.get("/options", response_model=GroupOptionsResponse, summary="Selectable users, managers, projects, and departments")
def group_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    return GroupOptionsResponse(
        users=[_to_user_option(user) for user in _visible_users(db, current_user)],
        managers=[_to_manager_option(user) for user in _visible_managers(db, current_user)],
        projects=[_to_project_option(project) for project in _visible_projects(db, current_user)],
        departments=[
            GroupOption(
                id=f"department:{name}",
                label=name,
                member_type="department",
                department_name=name,
            )
            for name in _visible_departments(db, current_user)
        ],
    )


@router.get("", response_model=GroupListResponse, summary="List custom groups with group-wise productivity data")
def list_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    groups = db.query(CustomGroup).options(
        joinedload(CustomGroup.parent_group),
        joinedload(CustomGroup.members).joinedload(CustomGroupMember.user),
        joinedload(CustomGroup.members).joinedload(CustomGroupMember.manager_user),
        joinedload(CustomGroup.members).joinedload(CustomGroupMember.project),
    ).order_by(CustomGroup.category_name.asc(), CustomGroup.name.asc()).all()
    return GroupListResponse(items=[_to_group_response(db, current_user, group) for group in groups if _can_view_group(current_user, group)])


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED, summary="Create a custom group")
def create_group(
    payload: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    if not payload.members:
        raise HTTPException(status_code=400, detail="At least one member is required")

    group = CustomGroup(
        name=payload.name.strip(),
        category_name=payload.category_name.strip(),
        description=(payload.description or "").strip() or None,
        parent_group_id=_validated_parent_group_id(db, current_user, payload.parent_group_id),
        leader_user_id=_validated_leader_id(db, current_user, payload.leader_user_id),
        leader_title=(payload.leader_title or "").strip() or None,
        created_by=current_user.id,
    )
    db.add(group)
    db.flush()

    _replace_group_members(db, current_user, group, payload.members)

    db.commit()
    stored = _load_group(db, group.id)
    return _to_group_response(db, current_user, stored)


@router.put("/{group_id}", response_model=GroupResponse, summary="Update a custom group")
def update_group(
    group_id: int,
    payload: GroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    group = db.query(CustomGroup).filter(CustomGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if not _can_view_group(current_user, group):
        raise HTTPException(status_code=403, detail="Not allowed to update this group")
    if not payload.members:
        raise HTTPException(status_code=400, detail="At least one member is required")

    group.name = payload.name.strip()
    group.category_name = payload.category_name.strip()
    group.description = (payload.description or "").strip() or None
    group.parent_group_id = _validated_parent_group_id(db, current_user, payload.parent_group_id, group.id)
    group.leader_user_id = _validated_leader_id(db, current_user, payload.leader_user_id)
    group.leader_title = (payload.leader_title or "").strip() or None

    _replace_group_members(db, current_user, group, payload.members)
    db.commit()
    stored = _load_group(db, group.id)
    return _to_group_response(db, current_user, stored)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a custom group")
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    group = db.query(CustomGroup).filter(CustomGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if not _can_view_group(current_user, group):
        raise HTTPException(status_code=403, detail="Not allowed to delete this group")
    db.delete(group)
    db.commit()


def _build_member(db: Session, current_user: User, group_id: int, item) -> CustomGroupMember:
    member = CustomGroupMember(
        group_id=group_id,
        member_type=item.member_type,
        label_override=(item.label_override or "").strip() or None,
        sort_order=item.sort_order,
    )
    if item.member_type == "user":
        user = db.query(User).filter(
            User.id == item.user_id,
            User.is_active.is_(True),
            User.is_monitoring_subject.is_(True),
        ).first()
        if not user or not _can_view_user(current_user, user):
            raise HTTPException(status_code=400, detail="Invalid user member")
        member.user_id = user.id
    elif item.member_type == "manager":
        manager_user = db.query(User).filter(
            User.id == item.manager_user_id,
            User.is_active.is_(True),
            User.is_monitoring_subject.is_(True),
        ).first()
        if not manager_user or not _can_view_user(current_user, manager_user):
            raise HTTPException(status_code=400, detail="Invalid manager member")
        member.manager_user_id = manager_user.id
    elif item.member_type == "project":
        project = db.query(Project).filter(Project.id == item.project_id).first()
        if not project or not _can_view_project(current_user, project):
            raise HTTPException(status_code=400, detail="Invalid project member")
        member.project_id = project.id
    elif item.member_type == "department":
        department_name = (item.department_name or "").strip()
        if not department_name:
            raise HTTPException(status_code=400, detail="department_name is required for department members")
        member.department_name = department_name
    else:
        raise HTTPException(status_code=400, detail="Unsupported member_type")
    return member


def _replace_group_members(db: Session, current_user: User, group: CustomGroup, members_payload: list) -> None:
    db.query(CustomGroupMember).filter(CustomGroupMember.group_id == group.id).delete()
    db.flush()

    created: dict[str, CustomGroupMember] = {}
    pending_parents: list[tuple[CustomGroupMember, str]] = []
    for item in members_payload:
        member = _build_member(db, current_user, group.id, item)
        db.add(member)
        db.flush()
        created[item.client_key] = member
        if item.parent_client_key:
            pending_parents.append((member, item.parent_client_key))

    for member, parent_key in pending_parents:
        parent = created.get(parent_key)
        if parent is None:
            raise HTTPException(status_code=400, detail=f"Unknown parent member key: {parent_key}")
        member.parent_member_id = parent.id


def _validated_leader_id(db: Session, current_user: User, leader_user_id: int | None) -> int | None:
    if leader_user_id is None:
        return None
    leader = db.query(User).filter(
        User.id == leader_user_id,
        User.is_active.is_(True),
        User.is_monitoring_subject.is_(True),
    ).first()
    if not leader or not _can_view_user(current_user, leader):
        raise HTTPException(status_code=400, detail="Invalid leader user")
    return leader.id


def _load_group(db: Session, group_id: int) -> CustomGroup | None:
    return db.query(CustomGroup).options(
        joinedload(CustomGroup.parent_group),
        joinedload(CustomGroup.members).joinedload(CustomGroupMember.user),
        joinedload(CustomGroup.members).joinedload(CustomGroupMember.manager_user),
        joinedload(CustomGroup.members).joinedload(CustomGroupMember.project),
    ).filter(CustomGroup.id == group_id).first()


def _to_group_response(db: Session, current_user: User, group: CustomGroup) -> GroupResponse:
    employee_counts = _member_employee_counts(db, current_user, group.members)
    child_counts = defaultdict(int)
    leader = db.query(User).filter(User.id == group.leader_user_id).first() if group.leader_user_id else None
    user_ids = _resolve_group_user_ids(db, current_user, group.members)
    if leader and leader.is_active and leader.is_monitoring_subject and _can_view_user(current_user, leader):
        user_ids.add(leader.id)
    for member in group.members:
        if member.parent_member_id:
            child_counts[member.parent_member_id] += 1
    return GroupResponse(
        id=group.id,
        name=group.name,
        category_name=group.category_name,
        description=group.description,
        parent_group_id=group.parent_group_id,
        parent_group_name=group.parent_group.name if group.parent_group else None,
        leader_user_id=group.leader_user_id,
        leader_name=(leader.full_name or leader.username) if leader else None,
        leader_title=group.leader_title,
        created_by=group.created_by,
        created_at=group.created_at,
        members=[
            GroupMemberResponse(
                id=member.id,
                parent_member_id=member.parent_member_id,
                member_type=member.member_type,
                user_id=member.user_id,
                manager_user_id=member.manager_user_id,
                project_id=member.project_id,
                department_name=member.department_name,
                label_override=member.label_override,
                display_label=_member_label(member),
                employee_count=employee_counts.get(member.id, 0),
                child_count=child_counts.get(member.id, 0),
            )
            for member in sorted(group.members, key=lambda item: (item.sort_order, item.id))
        ],
        summary=_group_summary(db, user_ids),
    )


def _group_summary(db: Session, user_ids: set[int]) -> GroupSummaryResponse:
    if not user_ids:
        return GroupSummaryResponse(
            employee_count=0,
            login_count=0,
            logout_count=0,
            productive_seconds=0,
            unproductive_seconds=0,
            active_seconds=0,
            idle_seconds=0,
            total_tracked_seconds=0,
            productivity_percent=0.0,
        )

    activities = db.query(ActivityLog).filter(ActivityLog.user_id.in_(list(user_ids))).all()
    login_count = sum(1 for item in activities if item.type == "login")
    logout_count = sum(1 for item in activities if item.type == "logout")
    productive = sum(int(item.duration or 0) for item in activities if item.type == "active")
    unproductive = sum(int(item.duration or 0) for item in activities if item.type == "unproductive")
    idle = sum(int(item.duration or 0) for item in activities if item.type == "idle")
    active = productive + unproductive
    total = active + idle
    return GroupSummaryResponse(
        employee_count=len(user_ids),
        login_count=login_count,
        logout_count=logout_count,
        productive_seconds=productive,
        unproductive_seconds=unproductive,
        active_seconds=active,
        idle_seconds=idle,
        total_tracked_seconds=total,
        productivity_percent=round((productive / total) * 100, 2) if total else 0.0,
    )


def _member_employee_counts(db: Session, current_user: User, members: list[CustomGroupMember]) -> dict[int, int]:
    return {member.id: len(_resolve_member_user_ids(db, current_user, member)) for member in members}


def _validated_parent_group_id(
    db: Session,
    current_user: User,
    parent_group_id: int | None,
    group_id: int | None = None,
) -> int | None:
    if parent_group_id is None:
        return None
    parent = db.query(CustomGroup).filter(CustomGroup.id == parent_group_id).first()
    if not parent or not _can_view_group(current_user, parent):
        raise HTTPException(status_code=400, detail="Invalid parent group")
    if group_id is not None and parent_group_id == group_id:
        raise HTTPException(status_code=400, detail="A group cannot be its own parent")
    if group_id is not None and _is_descendant_group(db, parent_group_id, group_id):
        raise HTTPException(status_code=400, detail="Parent group cannot be a descendant of the group")
    return parent.id


def _is_descendant_group(db: Session, candidate_parent_id: int, group_id: int) -> bool:
    current = db.query(CustomGroup).filter(CustomGroup.id == candidate_parent_id).first()
    visited: set[int] = set()
    while current and current.parent_group_id:
        if current.parent_group_id == group_id:
            return True
        if current.parent_group_id in visited:
            break
        visited.add(current.parent_group_id)
        current = db.query(CustomGroup).filter(CustomGroup.id == current.parent_group_id).first()
    return False


def _resolve_group_user_ids(db: Session, current_user: User, members: list[CustomGroupMember]) -> set[int]:
    user_ids: set[int] = set()
    for member in members:
        user_ids.update(_resolve_member_user_ids(db, current_user, member))
    return user_ids


def _resolve_member_user_ids(db: Session, current_user: User, member: CustomGroupMember) -> set[int]:
    if member.member_type == "user":
        return {member.user_id} if member.user_id and _can_view_user_id(db, current_user, member.user_id) else set()
    if member.member_type == "manager":
        rows = db.query(User.id).filter(
            User.manager_id == member.manager_user_id,
            User.is_active.is_(True),
            User.is_monitoring_subject.is_(True),
        ).all()
        return {row[0] for row in rows if _can_view_user_id(db, current_user, row[0])}
    if member.member_type == "project":
        rows = db.query(User.id).filter(
            User.project_id == member.project_id,
            User.is_active.is_(True),
            User.is_monitoring_subject.is_(True),
        ).all()
        return {row[0] for row in rows if _can_view_user_id(db, current_user, row[0])}
    if member.member_type == "department":
        rows = db.query(User.id).filter(
            User.department == member.department_name,
            User.is_active.is_(True),
            User.is_monitoring_subject.is_(True),
        ).all()
        return {row[0] for row in rows if _can_view_user_id(db, current_user, row[0])}
    return set()


def _member_label(member: CustomGroupMember) -> str:
    if member.label_override:
        return member.label_override
    if member.member_type == "user" and member.user:
        return member.user.full_name or member.user.username
    if member.member_type == "manager" and member.manager_user:
        return member.manager_user.full_name or member.manager_user.username
    if member.member_type == "project" and member.project:
        return member.project.name
    if member.member_type == "department":
        return member.department_name or "Department"
    return "Member"


def _visible_users(db: Session, current_user: User) -> list[User]:
    users = db.query(User).filter(
        User.is_active.is_(True),
        User.is_monitoring_subject.is_(True),
    ).order_by(User.full_name.asc(), User.username.asc()).all()
    return [user for user in users if _can_view_user(current_user, user)]


def _visible_managers(db: Session, current_user: User) -> list[User]:
    return _visible_users(db, current_user)


def _visible_projects(db: Session, current_user: User) -> list[Project]:
    projects = db.query(Project).order_by(Project.name.asc()).all()
    return [project for project in projects if _can_view_project(current_user, project)]


def _visible_departments(db: Session, current_user: User) -> list[str]:
    return sorted({(user.department or "").strip() for user in _visible_users(db, current_user) if (user.department or "").strip()})


def _can_view_group(current_user: User, group: CustomGroup) -> bool:
    if current_user.role == "admin":
        return True
    return group.created_by == current_user.id


def _can_view_user(current_user: User, target: User) -> bool:
    if not target.is_monitoring_subject or not target.is_active:
        return False
    if current_user.role == "admin":
        return True
    return target.id == current_user.id or target.manager_id == current_user.id


def _can_view_user_id(db: Session, current_user: User, user_id: int) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    return bool(user and _can_view_user(current_user, user))


def _can_view_project(current_user: User, project: Project) -> bool:
    if current_user.role == "admin":
        return True
    return project.manager_id == current_user.id


def _to_user_option(user: User) -> GroupOption:
    return GroupOption(id=f"user:{user.id}", label=user.full_name or user.username, member_type="user", ref_id=user.id)


def _to_manager_option(user: User) -> GroupOption:
    return GroupOption(id=f"manager:{user.id}", label=user.full_name or user.username, member_type="manager", ref_id=user.id)


def _to_project_option(project: Project) -> GroupOption:
    return GroupOption(id=f"project:{project.id}", label=project.name, member_type="project", ref_id=project.id)
