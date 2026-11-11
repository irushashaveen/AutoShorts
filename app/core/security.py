import hashlib
import hmac
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional
import jwt
from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "autoshorts_session"
JWT_ALGORITHM = "HS256"
SESSION_DURATION_DAYS = 7


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 200,000 rounds and random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200_000
    )
    return f"{salt}${key.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against stored salt$hash in constant time."""
    try:
        salt, expected_hash = hashed_password.split("$")
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            200_000
        )
        return hmac.compare_digest(key.hex(), expected_hash)
    except Exception as e:
        logger.warning(f"Password verification error: {e}")
        return False


def create_session_token(user_id: str, username: str, expires_in_days: int = SESSION_DURATION_DAYS) -> str:
    """Generate signed JWT session token."""
    expire = datetime.utcnow() + timedelta(days=expires_in_days)
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_session_token(token: str) -> Optional[dict]:
    """Verify and decode signed JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
        logger.debug(f"Invalid session token: {e}")
        return None


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Retrieve logged-in user from session cookie if present and valid."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        # Check Authorization header as fallback for API clients
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

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


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Enforce authentication; redirects to /login if unauthenticated on HTML endpoints."""
    user = get_current_user_optional(request, db)
    if not user:
        # Check if browser HTML request vs JSON API call
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header or request.method == "GET":
            # Redirect to login page
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/login"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user
