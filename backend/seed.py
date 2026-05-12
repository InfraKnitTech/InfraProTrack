"""
seed.py - Creates default admin user if not exists.
Run once: python seed.py
"""
from core.security import get_password_hash
from database import SessionLocal, create_all_tables
from models.user import User


def seed():
    create_all_tables()
    seed_defaults()


def seed_defaults():
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
                is_monitoring_subject=False,
            )
            db.add(admin)
            db.flush()
            print("Admin user created.")
        else:
            admin.username = "admin"
            admin.password = get_password_hash("pass123")
            admin.is_monitoring_subject = False
            print("Admin user already exists.")

        _remove_default_records(db)

        db.commit()
        print("Default admin profile verified.")
        print("Admin login: admin / pass123")
    finally:
        db.close()


def _remove_default_records(db):
    db.query(User).filter(User.role == "manager", User.username == "manager").delete(synchronize_session=False)
    db.query(User).filter(User.username == "manager").delete(synchronize_session=False)
    db.query(User).filter(User.username == "admin").update(
        {
            User.full_name: "Admin User",
            User.email: "admin@protrack.com",
            User.department: "Operations",
            User.is_monitoring_subject: False,
        },
        synchronize_session=False,
    )

    from models.monitoring import AppRule
    from models.project import Project

    default_project = db.query(Project).filter(Project.name == "Productivity Operations").first()
    if default_project:
        db.query(AppRule).filter(AppRule.project_id == default_project.id).delete(synchronize_session=False)
        db.delete(default_project)


if __name__ == "__main__":
    seed()
