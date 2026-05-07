from datetime import date
from typing import List
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.deps import get_db, get_current_user
from models.activity_log import ActivityLog
from models.agent import AgentDevice
from models.user import User
from schemas.dashboard import DashboardResponse, MetricCard, ChartPoint, AppUsagePoint

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def _fmt_hours(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m:02d}m"


def _extract_app(window_title: str) -> str:
    if not window_title:
        return "Unknown"
    title = window_title.lower()
    if "code" in title or "visual studio" in title:
        return "VS Code"
    if "chrome" in title:
        return "Chrome"
    if "firefox" in title:
        return "Firefox"
    if "excel" in title:
        return "Excel"
    if "word" in title:
        return "Word"
    if "youtube" in title:
        return "YouTube"
    if "powershell" in title or "terminal" in title or "cmd" in title:
        return "Terminal"
    if "teams" in title:
        return "MS Teams"
    if "slack" in title:
        return "Slack"
    parts = window_title.split(" — ")
    return parts[-1].strip()[:30] if parts else window_title[:30]


@router.get("/admin", response_model=DashboardResponse, summary="Admin org-wide dashboard")
def admin_dashboard(db: Session = Depends(get_db), _=Depends(get_current_user)):
    activities = db.query(ActivityLog).all()
    total_users = db.query(User).count()
    live_agent_count = db.query(AgentDevice).filter(
        AgentDevice.is_active.is_(True),
        AgentDevice.status == "online",
    ).count()

    total_productive = total_idle = total_unproductive = 0
    app_usage: dict = defaultdict(int)
    domain_usage: dict = defaultdict(int)
    daily: dict = defaultdict(lambda: {"productive": 0, "unproductive": 0})

    for act in activities:
        day_key = act.start_time.strftime("%d %b") if act.start_time else "Today"
        if act.type == "active":
            total_productive += act.duration
            daily[day_key]["productive"] += act.duration
        elif act.type == "unproductive":
            total_unproductive += act.duration
            daily[day_key]["unproductive"] += act.duration
        elif act.type == "idle":
            total_idle += act.duration

        app_name = _extract_app(act.window_title or "")
        app_usage[app_name] += act.duration

        if act.url:
            try:
                from urllib.parse import urlparse
                domain = urlparse(act.url).netloc or act.url[:50]
                domain_usage[domain] += act.duration
            except Exception:
                pass

    top_apps = sorted(
        [AppUsagePoint(name=k, value=v) for k, v in app_usage.items()],
        key=lambda x: x.value, reverse=True
    )[:10]

    top_domains = sorted(
        [AppUsagePoint(name=k, value=v) for k, v in domain_usage.items()],
        key=lambda x: x.value, reverse=True
    )[:10]

    chart_data = [
        ChartPoint(
            name=day,
            productive=round(vals["productive"] / 3600, 2),
            unproductive=round(vals["unproductive"] / 3600, 2),
        )
        for day, vals in sorted(daily.items())
    ] or [ChartPoint(name="Today", productive=0, unproductive=0)]

    return DashboardResponse(
        metrics=MetricCard(
            total_productive=_fmt_hours(total_productive),
            total_idle=_fmt_hours(total_idle),
            total_unproductive=_fmt_hours(total_unproductive),
            active_employees=live_agent_count,
            total_employees=total_users,
        ),
        productivity_data=chart_data,
        app_usage_data=top_apps if top_apps else [AppUsagePoint(name="No Data", value=0)],
        top_domains=top_domains,
    )


@router.get("/employee/{user_id}", summary="Employee self-view dashboard")
def employee_dashboard(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # employees can only view themselves; admins/managers can view anyone
    if current_user.role == "employee" and current_user.id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied")

    activities = db.query(ActivityLog).filter(ActivityLog.user_id == user_id).all()
    productive = sum(a.duration for a in activities if a.type == "active")
    idle = sum(a.duration for a in activities if a.type == "idle")
    unproductive = sum(a.duration for a in activities if a.type == "unproductive")

    app_usage: dict = defaultdict(int)
    for act in activities:
        app_usage[_extract_app(act.window_title or "")] += act.duration

    top_apps = sorted(app_usage.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "metrics": {
            "total_productive": _fmt_hours(productive),
            "total_idle": _fmt_hours(idle),
            "total_unproductive": _fmt_hours(unproductive),
        },
        "top_apps": [{"name": k, "value": v} for k, v in top_apps],
        "recent_activities": [
            {
                "id": a.id,
                "type": a.type,
                "app_name": a.app_name,
                "window_title": a.window_title,
                "duration": a.duration,
                "start_time": str(a.start_time),
            }
            for a in sorted(activities, key=lambda x: x.created_at or x.id, reverse=True)[:50]
        ],
    }
