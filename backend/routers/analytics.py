from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from core.deps import get_current_user, get_db
from models.usage import AppUsage, UrlUsage
from models.user import User
from schemas.analytics import AnalyticsListResponse, AnalyticsPoint

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


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
    if current_user.role == "admin":
        return True
    if current_user.role == "manager":
        return target.manager_id == current_user.id or (
            target.project is not None and target.project.manager_id == current_user.id
        )
    return target.id == current_user.id
