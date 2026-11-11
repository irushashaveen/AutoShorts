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
from app.models.user import User
from app.core.security import (
    hash_password,
    verify_password,
    create_session_token,
    get_current_user,
    get_current_user_optional,
    SESSION_COOKIE_NAME,
)

logger = logging.getLogger(__name__)

auth_router = APIRouter()
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@auth_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    """Render dark-mode login page. Redirects if already authenticated."""
    current_user = get_current_user_optional(request, db)
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "title": "Login · AutoShorts Control Plane",
            "error": None
        }
    )


@auth_router.post("/login", response_class=HTMLResponse)
def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Authenticate credentials and set secure HTTP-only session cookie."""
    user = db.query(User).filter(User.username == username.strip()).first()
    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
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

    # Update last login timestamp
    user.last_login_at = datetime.utcnow()
    db.commit()

    # Generate session token
    token = create_session_token(user.id, user.username)

    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    # Set secure cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG  # True in production HTTPS
    )
    return response


@auth_router.get("/logout")
def logout_action():
    """Clear session cookie and redirect to login."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return response


@auth_router.get("/admin/users", response_class=HTMLResponse)
def users_management_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Render user management administration interface."""
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


@auth_router.post("/admin/users/create")
def create_user_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: Optional[str] = Form(None),
    is_admin: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new operator or admin user."""
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

    new_user = User(
        username=clean_username,
        email=email.strip() if email else f"{clean_username}@reccalab.com",
        hashed_password=hash_password(password),
        is_admin=is_admin,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()

    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@auth_router.post("/admin/users/{user_id}/toggle")
def toggle_user_active(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enable or disable user account access (cannot disable own account)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own administrator account.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@auth_router.delete("/admin/users/{user_id}")
def delete_user_action(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Permanently delete a user account (cannot delete own account)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own administrator account.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return HTMLResponse(content="", status_code=200)
