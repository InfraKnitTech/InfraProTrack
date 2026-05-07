from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from core.deps import get_db, require_role
from models.monitoring import AppRule
from models.project import Project
from models.user import User
from schemas.rules import RuleCreate, RuleListResponse, RuleResponse, RuleUpdate

router = APIRouter(prefix="/api/rules", tags=["Rules"])


@router.get("", response_model=RuleListResponse, summary="List productive, unproductive, and prohibited rules")
def list_rules(
    category: str | None = Query(default=None, pattern="^(productive|unproductive|prohibited|neutral)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    query = db.query(AppRule).options(joinedload(AppRule.project)).order_by(AppRule.created_at.desc(), AppRule.id.desc())
    if category:
        query = query.filter(AppRule.category == category)

    rules = [rule for rule in query.all() if _can_view_rule(current_user, rule)]
    return RuleListResponse(items=[_to_rule_response(rule) for rule in rules])


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED, summary="Create a rule")
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    _validate_rule_payload(payload.app_name, payload.domain)
    project = _resolve_project(db, payload.project_id)
    rule = AppRule(
        app_name=_clean_str(payload.app_name),
        domain=_clean_str(payload.domain),
        category=payload.category,
        severity=payload.severity,
        project_id=project.id if project else None,
        created_by=current_user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _to_rule_response(rule)


@router.put("/{rule_id}", response_model=RuleResponse, summary="Update a rule")
def update_rule(
    rule_id: int,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    rule = db.query(AppRule).options(joinedload(AppRule.project)).filter(AppRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    next_app_name = _clean_str(payload.app_name) if payload.app_name is not None else rule.app_name
    next_domain = _clean_str(payload.domain) if payload.domain is not None else rule.domain
    _validate_rule_payload(next_app_name, next_domain)

    if payload.app_name is not None:
        rule.app_name = next_app_name
    if payload.domain is not None:
        rule.domain = next_domain
    if payload.category is not None:
        rule.category = payload.category
    if payload.severity is not None:
        rule.severity = payload.severity
    if "project_id" in payload.model_fields_set:
        project = _resolve_project(db, payload.project_id)
        rule.project_id = project.id if project else None

    db.commit()
    db.refresh(rule)
    return _to_rule_response(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a rule")
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    rule = db.query(AppRule).filter(AppRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()


def _can_view_rule(current_user: User, rule: AppRule) -> bool:
    if current_user.role == "admin":
        return True
    if rule.project is None:
        return True
    return rule.project.manager_id == current_user.id


def _validate_rule_payload(app_name: str | None, domain: str | None) -> None:
    if not app_name and not domain:
        raise HTTPException(status_code=400, detail="Either app_name or domain is required")


def _resolve_project(db: Session, project_id: int | None) -> Project | None:
    if project_id is None:
        return None
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _clean_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _to_rule_response(rule: AppRule) -> RuleResponse:
    project = getattr(rule, "project", None)
    return RuleResponse(
        id=rule.id,
        app_name=rule.app_name,
        domain=rule.domain,
        category=rule.category,
        severity=rule.severity,
        project_id=rule.project_id,
        project_name=project.name if project else None,
        created_by=rule.created_by,
        created_at=rule.created_at,
    )
