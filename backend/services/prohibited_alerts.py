from __future__ import annotations

import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from sqlalchemy.orm import Session

from core.config import email as email_config
from models.monitoring import ProhibitedUsageAlert
from models.project import Project, ProjectTask
from models.user import User

ALERT_DEDUP_WINDOW = timedelta(minutes=5)


def record_prohibited_usage(
    db: Session,
    *,
    user: User,
    resource_type: str,
    occurred_at: datetime,
    duration: int,
    app_name: str | None = None,
    domain: str | None = None,
    url: str | None = None,
    window_title: str | None = None,
) -> ProhibitedUsageAlert:
    project = _effective_project(db, user)
    manager = _designated_manager(db, user, project)
    lookup = {
        "user_id": user.id,
        "resource_type": resource_type,
    }
    if resource_type == "domain":
        lookup["domain"] = domain
    else:
        lookup["app_name"] = app_name

    recent_cutoff = occurred_at - ALERT_DEDUP_WINDOW
    alert = db.query(ProhibitedUsageAlert).filter(
        ProhibitedUsageAlert.user_id == lookup["user_id"],
        ProhibitedUsageAlert.resource_type == lookup["resource_type"],
        ProhibitedUsageAlert.last_seen_at >= recent_cutoff,
        ProhibitedUsageAlert.domain == lookup.get("domain") if resource_type == "domain" else ProhibitedUsageAlert.app_name == lookup.get("app_name"),
    ).order_by(ProhibitedUsageAlert.last_seen_at.desc()).first()

    if alert:
        alert.last_seen_at = occurred_at
        alert.duration = int(alert.duration or 0) + max(0, int(duration or 0))
        alert.occurrence_count = int(alert.occurrence_count or 0) + 1
        alert.url = url or alert.url
        alert.window_title = window_title or alert.window_title
        return alert

    alert = ProhibitedUsageAlert(
        user_id=user.id,
        manager_id=manager.id if manager else None,
        project_id=project.id if project else None,
        shift_id=user.shift_id,
        resource_type=resource_type,
        app_name=app_name,
        domain=domain,
        url=url,
        window_title=window_title,
        first_seen_at=occurred_at,
        last_seen_at=occurred_at,
        duration=max(0, int(duration or 0)),
        occurrence_count=1,
        manager_email=manager.email if manager else None,
        email_status="pending",
    )
    db.add(alert)
    db.flush()
    _send_manager_alert(alert, user, manager, project)
    return alert


def _send_manager_alert(
    alert: ProhibitedUsageAlert,
    user: User,
    manager: User | None,
    project: Project | None,
) -> None:
    if not manager or not manager.email:
        alert.email_status = "skipped_no_manager"
        alert.email_error = "No designated manager email available."
        return
    if not email_config.HOST or not email_config.FROM or not email_config.USER or not email_config.PASSWORD:
        alert.email_status = "skipped_email_not_configured"
        alert.email_error = "SMTP host, sender, username, or password is not configured."
        return

    resource = alert.domain if alert.resource_type == "domain" else alert.app_name
    subject = f"InfraProTrack prohibited {alert.resource_type} alert: {user.full_name or user.username}"
    body = (
        f"Employee: {user.full_name or user.username} ({user.username})\n"
        f"Project: {project.name if project else 'Unassigned Project'}\n"
        f"Manager: {manager.full_name or manager.username}\n"
        f"Resource type: {alert.resource_type}\n"
        f"Resource: {resource or '-'}\n"
        f"Window title: {alert.window_title or '-'}\n"
        f"URL: {alert.url or '-'}\n"
        f"Detected at: {alert.first_seen_at}\n"
        "\nReview this prohibited access event in InfraProTrack reports."
    )
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email_config.FROM
    message["To"] = manager.email
    message.set_content(body)

    try:
        if email_config.SECURE:
            server = smtplib.SMTP_SSL(email_config.HOST, email_config.PORT, timeout=10)
        else:
            server = smtplib.SMTP(email_config.HOST, email_config.PORT, timeout=10)
        with server:
            if not email_config.SECURE:
                try:
                    server.starttls()
                except smtplib.SMTPException:
                    pass
            server.login(email_config.USER, email_config.PASSWORD)
            server.send_message(message)
        alert.email_status = "sent"
        alert.email_error = None
    except Exception as exc:
        alert.email_status = "failed"
        alert.email_error = str(exc)[:1000]


def _effective_project(db: Session, user: User) -> Project | None:
    if user.project:
        return user.project
    managed = db.query(Project).filter(Project.manager_id == user.id).order_by(Project.created_at.desc()).first()
    if managed:
        return managed
    direct = db.query(Project).join(ProjectTask, ProjectTask.project_id == Project.id).filter(
        ProjectTask.employee_user_id == user.id,
    ).order_by(ProjectTask.created_at.desc()).first()
    if direct:
        return direct
    manager_task = db.query(Project).join(ProjectTask, ProjectTask.project_id == Project.id).filter(
        ProjectTask.manager_user_id == user.id,
    ).order_by(ProjectTask.created_at.desc()).first()
    if manager_task:
        return manager_task
    if user.manager_id:
        return db.query(Project).join(ProjectTask, ProjectTask.project_id == Project.id).filter(
            ProjectTask.manager_user_id == user.manager_id,
        ).order_by(ProjectTask.created_at.desc()).first()
    return None


def _designated_manager(db: Session, user: User, project: Project | None) -> User | None:
    if user.manager:
        return user.manager
    if project and project.manager:
        return project.manager
    if project and project.manager_id:
        return db.query(User).filter(User.id == project.manager_id).first()
    return None
