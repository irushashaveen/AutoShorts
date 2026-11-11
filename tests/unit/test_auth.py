import pytest
from datetime import datetime
from unittest.mock import MagicMock
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.core.security import (
    hash_password,
    verify_password,
    create_session_token,
    decode_session_token,
    LoginRateLimiter,
    login_rate_limiter,
    SESSION_COOKIE_NAME,
    SESSION_DURATION_SECONDS,
)
from app.core.deps import (
    get_current_user_optional,
    get_current_user,
    require_role,
    get_client_ip,
)
from app.web.auth_router import (
    login_page,
    login_action,
    logout_action,
    users_management_page,
    create_user_action,
    toggle_user_active,
    delete_user_action,
)
from app.cli import create_admin, create_operator, reset_password, list_users


@pytest.fixture
def test_admin_user(db_session: Session) -> User:
    """Fixture providing a persisted admin user."""
    user = User(
        username="testadmin",
        email="testadmin@reccalab.com",
        hashed_password=hash_password("adminpass123"),
        role=UserRole.ADMIN,
        is_admin=True,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_operator_user(db_session: Session) -> User:
    """Fixture providing a persisted operator user."""
    user = User(
        username="testoperator",
        email="testoperator@reccalab.com",
        hashed_password=hash_password("operatorpass123"),
        role=UserRole.OPERATOR,
        is_admin=False,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_password_hashing_and_salting():
    pwd = "supersecretpassword"
    hash1 = hash_password(pwd)
    hash2 = hash_password(pwd)

    assert "$" in hash1
    assert hash1 != hash2  # Unique 16-byte random salt per call
    assert verify_password(pwd, hash1) is True
    assert verify_password(pwd, hash2) is True
    assert verify_password("wrongpassword", hash1) is False
    assert verify_password("wrongpassword", "invalid_format") is False
    assert verify_password("", "") is False


def test_session_token_creation_and_decoding():
    user_id = "user_123"
    username = "admin"
    token = create_session_token(user_id, username, role="admin", expires_in_seconds=3600)
    assert isinstance(token, str)

    payload = decode_session_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["username"] == username
    assert payload["role"] == "admin"
    assert "exp" in payload

    # Tampered token verification
    invalid_token = token[:-5] + "abcde"
    assert decode_session_token(invalid_token) is None


def test_rate_limiter_lockout_after_5_failures():
    limiter = LoginRateLimiter(max_attempts=5, window_seconds=900)
    test_ip = "192.168.1.100"

    limiter.reset(test_ip)
    assert limiter.is_rate_limited(test_ip) == (False, 0)

    # 4 failures - not locked
    for i in range(4):
        count = limiter.record_failure(test_ip)
        assert count == i + 1
        is_blocked, _ = limiter.is_rate_limited(test_ip)
        assert is_blocked is False

    # 5th failure - locks out
    limiter.record_failure(test_ip)
    is_blocked, remaining = limiter.is_rate_limited(test_ip)
    assert is_blocked is True
    assert remaining > 0

    # Reset upon valid login clears lockout
    limiter.reset(test_ip)
    is_blocked_after, _ = limiter.is_rate_limited(test_ip)
    assert is_blocked_after is False


def test_rbac_require_role(test_admin_user, test_operator_user):
    admin_checker = require_role("admin")
    operator_checker = require_role("operator")

    # Admin passes both admin and operator checks
    assert admin_checker(current_user=test_admin_user) == test_admin_user
    assert operator_checker(current_user=test_admin_user) == test_admin_user

    # Operator passes operator check
    assert operator_checker(current_user=test_operator_user) == test_operator_user

    # Operator fails admin check with 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        admin_checker(current_user=test_operator_user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


def test_get_current_user_from_cookie(test_admin_user, db_session):
    token = create_session_token(test_admin_user.id, test_admin_user.username, role="admin")
    req = MagicMock(spec=Request)
    req.cookies = {SESSION_COOKIE_NAME: token}
    req.headers = {}

    user = get_current_user_optional(req, db=db_session)
    assert user is not None
    assert user.id == test_admin_user.id
    assert user.username == "testadmin"

    # Enforce current user
    enforced = get_current_user(req, db=db_session)
    assert enforced.id == test_admin_user.id


def test_get_current_user_unauthenticated_redirect(db_session):
    req = MagicMock(spec=Request)
    req.cookies = {}
    req.headers = {"accept": "text/html"}
    req.method = "GET"

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(req, db=db_session)
    assert exc_info.value.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert exc_info.value.headers["Location"] == "/login"


def test_login_action_success_and_cookie_attributes(test_admin_user, db_session):
    req = MagicMock(spec=Request)
    req.client = MagicMock()
    req.client.host = "10.0.0.1"
    req.headers = {}

    login_rate_limiter.reset("10.0.0.1")

    response = login_action(
        request=req,
        username="testadmin",
        password="adminpass123",
        db=db_session
    )
    assert isinstance(response, RedirectResponse)
    assert response.status_code == status.HTTP_303_SEE_OTHER
    assert response.headers["location"] == "/"

    # Cookie attributes validation
    set_cookie_header = response.headers.get("set-cookie")
    assert set_cookie_header is not None
    assert SESSION_COOKIE_NAME in set_cookie_header
    assert "httponly" in set_cookie_header.lower()
    assert "samesite=lax" in set_cookie_header.lower()
    assert f"max-age={SESSION_DURATION_SECONDS}" in set_cookie_header.lower()


def test_login_action_rate_limiting_enforcement(test_admin_user, db_session):
    test_ip = "172.16.0.5"
    req = MagicMock(spec=Request)
    req.client = MagicMock()
    req.client.host = test_ip
    req.headers = {}

    login_rate_limiter.reset(test_ip)

    # 5 failed attempts
    for _ in range(5):
        resp = login_action(
            request=req,
            username="testadmin",
            password="wrongpassword",
            db=db_session
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # 6th attempt should be blocked with 429 Too Many Requests
    blocked_resp = login_action(
        request=req,
        username="testadmin",
        password="adminpass123",
        db=db_session
    )
    assert blocked_resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Too many failed login attempts" in blocked_resp.body.decode()

    # Clean up rate limiter
    login_rate_limiter.reset(test_ip)


def test_logout_action():
    response = logout_action()
    assert isinstance(response, RedirectResponse)
    assert response.status_code == status.HTTP_303_SEE_OTHER
    assert response.headers["location"] == "/login"
    assert SESSION_COOKIE_NAME in response.headers.get("set-cookie", "")


def test_admin_user_management_lifecycle(test_admin_user, db_session):
    req = MagicMock(spec=Request)

    # 1. List users
    list_resp = users_management_page(request=req, current_user=test_admin_user, db=db_session)
    assert list_resp.status_code == 200
    assert len(list_resp.context["users"]) >= 1

    # 2. Create new operator user
    create_resp = create_user_action(
        request=req,
        username="new_operator",
        password="operator_pass_456",
        email="new_operator@reccalab.com",
        role="operator",
        current_user=test_admin_user,
        db=db_session
    )
    assert create_resp.status_code == status.HTTP_303_SEE_OTHER

    new_user = db_session.query(User).filter(User.username == "new_operator").first()
    assert new_user is not None
    assert new_user.role == UserRole.OPERATOR
    assert new_user.is_admin is False
    assert new_user.is_active is True

    # 3. Toggle user active status
    toggle_user_active(user_id=new_user.id, current_user=test_admin_user, db=db_session)
    db_session.refresh(new_user)
    assert new_user.is_active is False

    # 4. Cannot deactivate self
    with pytest.raises(HTTPException) as exc_info:
        toggle_user_active(user_id=test_admin_user.id, current_user=test_admin_user, db=db_session)
    assert exc_info.value.status_code == 400

    # 5. Delete second user
    del_resp = delete_user_action(user_id=new_user.id, current_user=test_admin_user, db=db_session)
    assert del_resp.status_code == 200
    assert db_session.query(User).filter(User.id == new_user.id).first() is None

    # 6. Cannot delete self
    with pytest.raises(HTTPException) as exc_info:
        delete_user_action(user_id=test_admin_user.id, current_user=test_admin_user, db=db_session)
    assert exc_info.value.status_code == 400
