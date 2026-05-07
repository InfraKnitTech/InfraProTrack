import os
import aiofiles
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from core.deps import get_db, get_current_user
from models.activity_log import ActivityLog
from models.usage import AppUsage, UrlUsage
from models.monitoring import IdleLog, Screenshot, AppRule

router = APIRouter(prefix="/api/telemetry", tags=["Telemetry"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _classify_app(app_name: str, window_title: str, db: Session) -> str:
    """Check app_rules table to classify this app. Default: neutral."""
    if not app_name:
        return "neutral"
    rule = db.query(AppRule).filter(
        AppRule.app_name.ilike(f"%{app_name}%")
    ).first()
    return rule.category if rule else "neutral"


@router.post("/", summary="Agent telemetry ingestion (JSON)")
async def ingest_telemetry(
    type: str = Form(...),
    app_name: str = Form(None),
    window_title: str = Form(None),
    url: str = Form(None),
    file_path: str = Form(None),
    start_time: str = Form(None),
    end_time: str = Form(None),
    duration: int = Form(0),
    screenshot: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    parsed_start = datetime.fromisoformat(start_time) if start_time else None
    parsed_end = datetime.fromisoformat(end_time) if end_time else None

    # Classify and possibly override type
    category = _classify_app(app_name or "", window_title or "", db)
    if category == "prohibited":
        effective_type = "unproductive"
        # TODO: trigger alert email to manager here
    elif category == "unproductive":
        effective_type = "unproductive"
    else:
        effective_type = type

    # Save to activity_logs
    activity = ActivityLog(
        user_id=current_user.id,
        type=effective_type,
        app_name=app_name,
        window_title=window_title,
        url=url,
        file_path=file_path,
        start_time=parsed_start,
        end_time=parsed_end,
        duration=duration,
    )
    db.add(activity)
    db.flush()  # get activity.id before commit

    # Save idle log entry
    if effective_type == "idle":
        idle = IdleLog(
            user_id=current_user.id,
            start_time=parsed_start or datetime.utcnow(),
            duration=duration,
        )
        db.add(idle)

    # Save screenshot if provided
    screenshot_path = None
    if screenshot and screenshot.filename:
        filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}_{screenshot.filename}"
        screenshot_path = os.path.join(UPLOAD_DIR, filename)
        async with aiofiles.open(screenshot_path, "wb") as f:
            content = await screenshot.read()
            await f.write(content)

        db.add(Screenshot(
            user_id=current_user.id,
            file_path=screenshot_path,
            trigger_reason="agent_upload",
            activity_log_id=activity.id,
        ))

    db.commit()
    return {"message": "Telemetry saved", "activity_id": activity.id}


@router.post("/idle-reason", summary="Employee submits reason for idle time")
def submit_idle_reason(
    idle_log_id: int = Form(...),
    reason: str = Form(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    log = db.query(IdleLog).filter(
        IdleLog.id == idle_log_id,
        IdleLog.user_id == current_user.id
    ).first()
    if not log:
        raise HTTPException(status_code=404, detail="Idle log not found")
    log.reason = reason
    db.commit()
    return {"message": "Reason saved"}
