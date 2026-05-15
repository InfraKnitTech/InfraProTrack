from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from core.time_utils import now_ist
from models.activity_log import ActivityLog
from models.monitoring import ProductivityScore, ProhibitedUsageAlert
from models.user import User


@dataclass
class CalculatedProductivityIndex:
    user_id: int
    score_date: datetime
    score: int
    productive_pct: int
    idle_pct: int
    unproductive_pct: int
    login_time: datetime | None
    logout_time: datetime | None


def recalculate_productivity_index(
    db: Session,
    target_date: date | None = None,
    user_ids: list[int] | None = None,
) -> list[ProductivityScore]:
    day = target_date or now_ist().date()
    start_at = datetime.combine(day, time.min)
    end_at = start_at + timedelta(days=1)

    query = db.query(User.id).filter(
        User.is_monitoring_subject.is_(True),
        User.is_active.is_(True),
    )
    if user_ids:
        query = query.filter(User.id.in_(user_ids))
    visible_user_ids = [row[0] for row in query.all()]
    if not visible_user_ids:
        return []

    calculated = _calculate_scores(db, visible_user_ids, start_at, end_at)
    stored: list[ProductivityScore] = []
    for row in calculated:
        score_row = db.query(ProductivityScore).filter(
            ProductivityScore.user_id == row.user_id,
            ProductivityScore.date == row.score_date,
        ).first()
        if not score_row:
            score_row = ProductivityScore(user_id=row.user_id, date=row.score_date)
            db.add(score_row)

        score_row.score = row.score
        score_row.productive_pct = row.productive_pct
        score_row.idle_pct = row.idle_pct
        score_row.unproductive_pct = row.unproductive_pct
        score_row.login_time = row.login_time
        score_row.logout_time = row.logout_time
        stored.append(score_row)

    db.flush()
    return stored


def _calculate_scores(
    db: Session,
    user_ids: list[int],
    start_at: datetime,
    end_at: datetime,
) -> list[CalculatedProductivityIndex]:
    activity_start = func.coalesce(ActivityLog.start_time, ActivityLog.created_at)
    activity_end = func.coalesce(ActivityLog.end_time, ActivityLog.start_time, ActivityLog.created_at)
    duration = func.coalesce(ActivityLog.duration, 0)

    rows = db.query(
        ActivityLog.user_id.label("user_id"),
        func.min(case((ActivityLog.type == "login", activity_start), else_=None)).label("login_time"),
        func.max(case((ActivityLog.type == "logout", activity_start), else_=None)).label("logout_time"),
        func.min(activity_start).label("first_activity"),
        func.max(activity_end).label("last_activity"),
        func.sum(case((ActivityLog.type == "active", duration), else_=0)).label("productive_seconds"),
        func.sum(case((ActivityLog.type == "unproductive", duration), else_=0)).label("unproductive_seconds"),
        func.sum(case((ActivityLog.type == "idle", duration), else_=0)).label("idle_seconds"),
    ).filter(
        ActivityLog.user_id.in_(user_ids),
        ActivityLog.start_time >= start_at,
        ActivityLog.start_time < end_at,
    ).group_by(ActivityLog.user_id).all()

    prohibited_counts = _prohibited_counts(db, user_ids, start_at, end_at)
    calculated: list[CalculatedProductivityIndex] = []
    for row in rows:
        productive_seconds = int(row.productive_seconds or 0)
        unproductive_seconds = int(row.unproductive_seconds or 0)
        idle_seconds = int(row.idle_seconds or 0)
        total_seconds = productive_seconds + unproductive_seconds + idle_seconds
        if total_seconds <= 0:
            productive_pct = idle_pct = unproductive_pct = 0
            score = 0
        else:
            productive_pct = round((productive_seconds / total_seconds) * 100)
            idle_pct = round((idle_seconds / total_seconds) * 100)
            unproductive_pct = round((unproductive_seconds / total_seconds) * 100)
            prohibited_penalty = min(20, prohibited_counts.get(row.user_id, 0) * 5)
            score = round(100 - (unproductive_pct * 0.7) - (idle_pct * 0.4) - prohibited_penalty)
            score = max(0, min(100, score))

        calculated.append(CalculatedProductivityIndex(
            user_id=row.user_id,
            score_date=start_at,
            score=score,
            productive_pct=productive_pct,
            idle_pct=idle_pct,
            unproductive_pct=unproductive_pct,
            login_time=row.login_time or row.first_activity,
            logout_time=row.logout_time or row.last_activity,
        ))
    return calculated


def _prohibited_counts(
    db: Session,
    user_ids: list[int],
    start_at: datetime,
    end_at: datetime,
) -> dict[int, int]:
    rows = db.query(
        ProhibitedUsageAlert.user_id,
        func.coalesce(func.sum(ProhibitedUsageAlert.occurrence_count), 0),
    ).filter(
        ProhibitedUsageAlert.user_id.in_(user_ids),
        ProhibitedUsageAlert.last_seen_at >= start_at,
        ProhibitedUsageAlert.first_seen_at < end_at,
    ).group_by(ProhibitedUsageAlert.user_id).all()
    return {user_id: int(count or 0) for user_id, count in rows}
