from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from core.deps import get_current_user, get_db, require_role
from models.monitoring import ProductivityScore
from models.user import User
from schemas.productivity_index import (
    ProductivityIndexRecalculateResponse,
    ProductivityIndexRow,
    ProductivityIndexSummaryResponse,
)
from services.productivity_index import recalculate_productivity_index

router = APIRouter(prefix="/api/productivity-index", tags=["Productivity Index"])


@router.get("/summary", response_model=ProductivityIndexSummaryResponse)
def productivity_index_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = _visible_score_rows(db, current_user)
    return ProductivityIndexSummaryResponse(
        average_score=_average_score(rows),
        employee_count=len(rows),
        rows=[_row_out(row) for row in rows],
    )


@router.post("/recalculate", response_model=ProductivityIndexRecalculateResponse)
def recalculate_index(
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    user_ids = _visible_user_ids(db, current_user)
    recalculate_productivity_index(db, target_date=target_date, user_ids=user_ids)
    db.commit()
    rows = _visible_score_rows(db, current_user, target_date=target_date)
    return ProductivityIndexRecalculateResponse(
        recalculated=len(rows),
        rows=[_row_out(row) for row in rows],
    )


def _visible_score_rows(
    db: Session,
    current_user: User,
    target_date: date | None = None,
) -> list[ProductivityScore]:
    query = db.query(ProductivityScore).options(joinedload(ProductivityScore.user)).join(
        User,
        ProductivityScore.user_id == User.id,
    ).filter(
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    )
    if target_date:
        start_at = datetime.combine(target_date, time.min)
        end_at = start_at + timedelta(days=1)
        query = query.filter(ProductivityScore.date >= start_at, ProductivityScore.date < end_at)
    rows = query.order_by(ProductivityScore.date.desc(), ProductivityScore.score.desc()).all()

    latest_by_user: dict[int, ProductivityScore] = {}
    for row in rows:
        if row.user_id in latest_by_user:
            continue
        if _can_view_user(current_user, row.user):
            latest_by_user[row.user_id] = row
    return list(latest_by_user.values())


def _visible_user_ids(db: Session, current_user: User) -> list[int]:
    users = db.query(User).filter(
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    ).all()
    return [user.id for user in users if _can_view_user(current_user, user)]


def _can_view_user(current_user: User, target: User | None) -> bool:
    if target is None or not target.is_monitoring_subject or not target.is_active:
        return False
    if current_user.role == "admin":
        return True
    if current_user.role == "manager":
        return target.manager_id == current_user.id or (
            target.project is not None and target.project.manager_id == current_user.id
        )
    return target.id == current_user.id


def _row_out(row: ProductivityScore) -> ProductivityIndexRow:
    user = row.user
    return ProductivityIndexRow(
        employee_id=row.user_id,
        employee_name=user.full_name or user.username,
        username=user.username,
        date=row.date,
        score=int(row.score or 0),
        productive_pct=int(row.productive_pct or 0),
        idle_pct=int(row.idle_pct or 0),
        unproductive_pct=int(row.unproductive_pct or 0),
        login_time=row.login_time,
        logout_time=row.logout_time,
    )


def _average_score(rows: list[ProductivityScore]) -> float:
    if not rows:
        return 0.0
    return round(sum(int(row.score or 0) for row in rows) / len(rows), 2)
