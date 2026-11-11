import logging
from typing import Optional, List, Callable
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.core.security import (
    decode_session_token,
    SESSION_COOKIE_NAME,
)

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """
    Extract client real IP address supporting Nginx reverse proxy headers:
    1. X-Forwarded-For (first IP in comma-separated list)
    2. X-Real-IP
    3. Direct client host fallback
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host.strip()

    return "127.0.0.1"


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Retrieve authenticated User entity from signed session cookie or Authorization header.
    Returns None if session is absent, expired, or invalid.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        # Check Bearer authorization header as fallback for external scripts / CLI
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        return None

    payload = decode_session_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Enforces authentication across protected endpoints.
    - On browser HTML GET requests: Redirects seamlessly to /login with 307.
    - On API / HTMX / POST requests: Raises 401 Unauthorized.
    """
    user = get_current_user_optional(request, db)
    if not user:
        accept_header = request.headers.get("accept", "")
        # If user visits dashboard directly in a browser via GET, redirect to login
        if request.method == "GET" and ("text/html" in accept_header or "*/*" in accept_header):
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/login"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in."
        )
    return user


def require_role(*allowed_roles: str) -> Callable:
    """
    Role-Based Access Control (RBAC) dependency factory.
    Enforces that the authenticated user possesses one of the allowed roles.
    Administrator ('admin') users implicitly possess all operational permissions.
    Raises: HTTP 403 Forbidden if user lacks required role.
    """
    normalized_allowed = [r.lower() for r in allowed_roles]

    def role_verifier(current_user: User = Depends(get_current_user)) -> User:
        user_role_str = (
            current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        ).lower()

        # Admin satisfies all role requirements
        if user_role_str == "admin" or current_user.is_admin:
            return current_user

        if user_role_str not in normalized_allowed:
            logger.warning(
                f"Access denied: User '{current_user.username}' with role '{user_role_str}' "
                f"attempted to access endpoint requiring {allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Action requires one of the following roles: {', '.join(allowed_roles)}"
            )

        return current_user

    return role_verifier
