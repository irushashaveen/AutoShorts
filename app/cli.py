import sys
import argparse
from datetime import datetime
from app.database import SessionLocal
from app.models import init_db
from app.models.user import User
from app.core.security import hash_password


def create_admin(username: str, password: str, email: str = "") -> None:
    """Create or reset an administrator account."""
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            existing.hashed_password = hash_password(password)
            if email:
                existing.email = email
            existing.is_admin = True
            existing.is_active = True
            db.commit()
            print(f"✅ Administrator '{username}' password successfully updated.")
            return

        new_user = User(
            username=username,
            email=email if email else f"{username}@reccalab.com",
            hashed_password=hash_password(password),
            is_admin=True,
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(new_user)
        db.commit()
        print(f"✅ Administrator '{username}' successfully created!")
    finally:
        db.close()


def list_users() -> None:
    """List all registered system users."""
    init_db()
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"\n--- AutoShorts Users ({len(users)}) ---")
        for u in users:
            status = "ACTIVE" if u.is_active else "DISABLED"
            role = "ADMIN" if u.is_admin else "USER"
            print(f"• ID: {u.id} | User: {u.username} | Email: {u.email} | Role: {role} | Status: {status}")
        print("------------------------------------\n")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="AutoShorts CLI Administration Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-admin
    admin_parser = subparsers.add_parser("create-admin", help="Create or update an administrator account")
    admin_parser.add_argument("--username", "-u", required=True, help="Admin username")
    admin_parser.add_argument("--password", "-p", required=True, help="Admin password")
    admin_parser.add_argument("--email", "-e", default="", help="Admin email (optional)")

    # list-users
    subparsers.add_parser("list-users", help="List all registered system users")

    args = parser.parse_args()

    if args.command == "create-admin":
        create_admin(args.username, args.password, args.email)
    elif args.command == "list-users":
        list_users()


if __name__ == "__main__":
    main()
