import logging
from datetime import datetime
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, Form, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.user import User, UserRole
from app.core.security import (
    hash_password,
    verify_password,
    create_session_token,
    login_rate_limiter,
    SESSION_COOKIE_NAME,
    SESSION_DURATION_SECONDS,
)
from app.core.deps import (
    get_client_ip,
    get_current_user,
    get_current_user_optional,
    require_role,
)

logger = logging.getLogger(__name__)

auth_router = APIRouter()
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@auth_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    """Render dark-mode login page. Redirects to dashboard if already authenticated."""
    current_user = get_current_user_optional(request, db)
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "title": "Login · AutoShorts Control Plane",
            "error": None,
            "username": ""
        }
    )


@auth_router.post("/login", response_class=HTMLResponse)
def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Authenticate user credentials with rate limiting and set secure HTTP-only session cookie.
    Enforces IP-based lockout after 5 failed attempts within a 15-minute window.
    """
    client_ip = get_client_ip(request)

    # 1. Check Rate Limit
    is_blocked, remaining_seconds = login_rate_limiter.is_rate_limited(client_ip)
    if is_blocked:
        minutes_remaining = max(1, (remaining_seconds + 59) // 60)
        logger.warning(f"Login rejected: IP {client_ip} is currently rate-limited ({remaining_seconds}s remaining).")
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "title": "Login · AutoShorts Control Plane",
                "error": f"Too many failed login attempts from your IP. Please try again in {minutes_remaining} minute(s).",
                "username": username
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )

    # 2. Query User Entity
    clean_username = username.strip()
    user = db.query(User).filter(User.username == clean_username).first()

    # 3. Validate Credentials and Active Status
    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
        current_failures = login_rate_limiter.record_failure(client_ip)
        logger.warning(
            f"Failed login attempt for '{clean_username}' from IP {client_ip} "
            f"(attempt {current_failures}/{login_rate_limiter.max_attempts})."
        )
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "title": "Login · AutoShorts Control Plane",
                "error": "Invalid username or password.",
                "username": username
            },
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # 4. Successful Authentication: Reset Rate Limiter & Update Timestamp
    login_rate_limiter.reset(client_ip)
    user.last_login_at = datetime.utcnow()
    db.commit()

    # 5. Mint Signed JWT Session Token
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    token = create_session_token(
        user_id=user.id,
        username=user.username,
        role=role_str,
        expires_in_seconds=SESSION_DURATION_SECONDS
    )

    # 6. Set Secure Session Cookie
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG  # True on production HTTPS (shorts.reccalab.com)
    )
    return response


@auth_router.get("/logout")
def logout_action():
    """Clear session cookie and redirect to login."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return response


# ---------------------------------------------------------------------------
# RBAC Protected User Management Routes (/users and /admin/users)
# ---------------------------------------------------------------------------

@auth_router.get("/users", response_class=HTMLResponse)
@auth_router.get("/admin/users", response_class=HTMLResponse)
def users_management_page(
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """
    Render user management administration interface (Admin role strictly required).
    """
    users = db.query(User).order_by(User.created_at.asc()).all()
    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "users": users,
            "current_user": current_user,
            "title": "User Management · AutoShorts",
            "message": None,
            "error": None
        }
    )


@auth_router.post("/users/create")
@auth_router.post("/admin/users/create")
def create_user_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: Optional[str] = Form(None),
    role: str = Form("operator"),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """
    Admin-only endpoint to register a new system operator or administrator.
    """
    clean_username = username.strip()
    existing = db.query(User).filter(User.username == clean_username).first()
    if existing:
        users = db.query(User).order_by(User.created_at.asc()).all()
        return templates.TemplateResponse(
            request=request,
            name="users.html",
            context={
                "users": users,
                "current_user": current_user,
                "title": "User Management · AutoShorts",
                "error": f"Username '{clean_username}' already exists."
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # Determine role
    target_role = UserRole.ADMIN if role.lower() == "admin" else UserRole.OPERATOR

    new_user = User(
        username=clean_username,
        email=email.strip() if email else f"{clean_username}@reccalab.com",
        hashed_password=hash_password(password),
        role=target_role,
        is_admin=(target_role == UserRole.ADMIN),
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()

    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)


@auth_router.post("/users/{user_id}/toggle")
@auth_router.post("/admin/users/{user_id}/toggle")
def toggle_user_active(
    user_id: str,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """
    Enable or disable user account access (Admins cannot deactivate themselves).
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own administrator account."
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = not user.is_active
    db.commit()
    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)


@auth_router.delete("/users/{user_id}")
@auth_router.delete("/admin/users/{user_id}")
def delete_user_action(
    user_id: str,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """
    Permanently delete a user account (Admins cannot delete themselves).
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own administrator account."
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.delete(user)
    db.commit()
    return HTMLResponse(content="", status_code=status.HTTP_200_OK)
