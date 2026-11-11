import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Ensure project root is in sys.path so CLI can run from anywhere
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.database import SessionLocal
from app.models import init_db
from app.models.user import User, UserRole
from app.core.security import hash_password


def create_user_account(username: str, password: str, role: UserRole, email: str = "") -> None:
    """Create or reset an account with specified role."""
    init_db()
    db = SessionLocal()
    try:
        clean_user = username.strip()
        existing = db.query(User).filter(User.username == clean_user).first()
        if existing:
            existing.hashed_password = hash_password(password)
            existing.role = role
            existing.is_admin = (role == UserRole.ADMIN)
            existing.is_active = True
            if email:
                existing.email = email.strip()
            db.commit()
            print(f"✅ User '{clean_user}' updated to role '{role.value}' with new password.")
            return

        new_user = User(
            username=clean_user,
            email=email.strip() if email else f"{clean_user}@reccalab.com",
            hashed_password=hash_password(password),
            role=role,
            is_admin=(role == UserRole.ADMIN),
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(new_user)
        db.commit()
        print(f"✅ User '{clean_user}' created with role '{role.value}' successfully!")
    finally:
        db.close()


def create_admin(username: str, password: str, email: str = "") -> None:
    """Create or update an administrator account."""
    create_user_account(username=username, password=password, role=UserRole.ADMIN, email=email)


def create_operator(username: str, password: str, email: str = "") -> None:
    """Create or update an operator account."""
    create_user_account(username=username, password=password, role=UserRole.OPERATOR, email=email)


def reset_password(username: str, password: str) -> None:
    """Reset password for an existing user."""
    init_db()
    db = SessionLocal()
    try:
        clean_user = username.strip()
        user = db.query(User).filter(User.username == clean_user).first()
        if not user:
            print(f"❌ User '{clean_user}' not found.")
            sys.exit(1)

        user.hashed_password = hash_password(password)
        db.commit()
        print(f"✅ Password for user '{clean_user}' successfully reset.")
    finally:
        db.close()


def list_users() -> None:
    """List all registered system users and their roles."""
    init_db()
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.asc()).all()
        print(f"\n================ AutoShorts Users ({len(users)}) ================")
        if not users:
            print("No users registered yet. Run 'create-admin' to bootstrap an administrator.")
        for u in users:
            status = "ACTIVE" if u.is_active else "DISABLED"
            role_str = u.role.value if hasattr(u.role, "value") else str(u.role)
            last_login = u.last_login_at.strftime('%Y-%m-%d %H:%M:%S UTC') if u.last_login_at else "Never"
            print(f"• [{role_str.upper():8s}] {u.username:16s} | Email: {u.email or 'N/A':24s} | Status: {status:8s} | Last Login: {last_login}")
        print("=================================================================\n")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="AutoShorts Security & User Administration CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-admin
    admin_parser = subparsers.add_parser("create-admin", help="Bootstrap or update an administrator account")
    admin_parser.add_argument("--username", "-u", required=True, help="Administrator username")
    admin_parser.add_argument("--password", "-p", required=True, help="Administrator password")
    admin_parser.add_argument("--email", "-e", default="", help="Administrator email address")

    # create-operator
    op_parser = subparsers.add_parser("create-operator", help="Create or update an operator account")
    op_parser.add_argument("--username", "-u", required=True, help="Operator username")
    op_parser.add_argument("--password", "-p", required=True, help="Operator password")
    op_parser.add_argument("--email", "-e", default="", help="Operator email address")

    # reset-password
    reset_parser = subparsers.add_parser("reset-password", help="Reset password for an existing user")
    reset_parser.add_argument("--username", "-u", required=True, help="Username to update")
    reset_parser.add_argument("--password", "-p", required=True, help="New password")

    # list-users
    subparsers.add_parser("list-users", help="List all registered system users")

    args = parser.parse_args()

    if args.command == "create-admin":
        create_admin(args.username, args.password, args.email)
    elif args.command == "create-operator":
        create_operator(args.username, args.password, args.email)
    elif args.command == "reset-password":
        reset_password(args.username, args.password)
    elif args.command == "list-users":
        list_users()


if __name__ == "__main__":
    main()
