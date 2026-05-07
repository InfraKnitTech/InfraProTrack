"""
seed.py - Creates default admin user if not exists.
Run once: python seed.py
"""
from core.security import get_password_hash
from database import SessionLocal, create_all_tables
from models.manager import Manager
from models.monitoring import AppRule
from models.project import Project
from models.shift import Shift
from models.user import User
from datetime import time


def seed():
    create_all_tables()
    db = SessionLocal()
    try:
        admin_email = "admin@protrack.com"
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                username="admin",
                full_name="Admin User",
                email=admin_email,
                password=get_password_hash("pass123"),
                role="admin",
                department="Operations",
            )
            db.add(admin)
            db.flush()
            print("Admin user created.")
        else:
            admin.username = "admin"
            admin.password = get_password_hash("pass123")
            print("Admin user already exists.")

        day_shift = _ensure_shift(db, "India Day Shift", time(9, 30), time(18, 30), "Asia/Kolkata")
        night_shift = _ensure_shift(db, "US Support Shift", time(20, 0), time(5, 0), "Asia/Kolkata", is_overnight=1)

        manager = _ensure_user(
            db,
            username="manager",
            full_name="Operations Manager",
            email="manager@protrack.com",
            password="manager123",
            role="manager",
            department="Delivery",
            shift_id=day_shift.id,
        )
        if not db.query(Manager).filter(Manager.user_id == manager.id).first():
            db.add(Manager(user_id=manager.id, department="Delivery", region="India"))

        project = db.query(Project).filter(Project.name == "Productivity Operations").first()
        if not project:
            project = Project(
                name="Productivity Operations",
                description="Baseline production monitoring project",
                client_name="Internal",
                manager_id=manager.id,
                status="active",
            )
            db.add(project)
            db.flush()

        _ensure_user(
            db,
            username="employee",
            full_name="Demo Employee",
            email="employee@protrack.com",
            password="employee123",
            role="employee",
            department="Delivery",
            manager_id=manager.id,
            project_id=project.id,
            shift_id=day_shift.id,
        )
        _ensure_user(
            db,
            username="night.employee",
            full_name="Night Shift Employee",
            email="night.employee@protrack.com",
            password="employee123",
            role="employee",
            department="Support",
            manager_id=manager.id,
            project_id=project.id,
            shift_id=night_shift.id,
        )

        for app_name, domain, category, severity in [
            ("Visual Studio Code", None, "productive", "low"),
            ("Microsoft Excel", None, "productive", "low"),
            ("Microsoft Teams", None, "productive", "low"),
            ("YouTube", "youtube.com", "unproductive", "medium"),
            ("Games", None, "prohibited", "high"),
        ]:
            exists = db.query(AppRule).filter(
                AppRule.app_name == app_name,
                AppRule.domain == domain,
            ).first()
            if not exists:
                db.add(AppRule(
                    app_name=app_name,
                    domain=domain,
                    category=category,
                    severity=severity,
                    project_id=project.id,
                    created_by=admin.id,
                ))

        db.commit()
        print("Baseline shifts, project, users, manager profile, and app rules verified.")
        print("Admin login: admin / pass123")
    finally:
        db.close()


def _ensure_shift(db, name, start_time, end_time, timezone, is_overnight=0):
    shift = db.query(Shift).filter(Shift.name == name).first()
    if shift:
        return shift
    shift = Shift(
        name=name,
        start_time=start_time,
        end_time=end_time,
        timezone=timezone,
        is_overnight=is_overnight,
    )
    db.add(shift)
    db.flush()
    return shift


def _ensure_user(db, username, full_name, email, password, role, department, **kwargs):
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        username=username,
        full_name=full_name,
        email=email,
        password=get_password_hash(password),
        role=role,
        department=department,
        **kwargs,
    )
    db.add(user)
    db.flush()
    return user


if __name__ == "__main__":
    seed()
