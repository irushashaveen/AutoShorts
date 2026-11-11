import pytest
from datetime import datetime
from unittest.mock import MagicMock
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import (
    hash_password,
    verify_password,
    create_session_token,
    decode_session_token,
    get_current_user_optional,
    get_current_user,
    SESSION_COOKIE_NAME,
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


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Fixture providing a persisted test user."""
    user = User(
        username="testadmin",
        email="testadmin@reccalab.com",
        hashed_password=hash_password("adminpass123"),
        is_admin=True,
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
    assert hash1 != hash2  # Unique salt per call
    assert verify_password(pwd, hash1) is True
    assert verify_password(pwd, hash2) is True
    assert verify_password("wrongpassword", hash1) is False
    assert verify_password("wrongpassword", "invalid_format") is False


def test_session_token_creation_and_decoding():
    user_id = "user_123"
    username = "admin"
    token = create_session_token(user_id, username, expires_in_days=1)
    assert isinstance(token, str)

    payload = decode_session_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["username"] == username
    assert "exp" in payload

    # Tampered token
    invalid_token = token[:-5] + "abcde"
    assert decode_session_token(invalid_token) is None


def test_get_current_user_from_cookie(test_user, db_session):
    token = create_session_token(test_user.id, test_user.username)
    req = MagicMock(spec=Request)
    req.cookies = {SESSION_COOKIE_NAME: token}
    req.headers = {}

    user = get_current_user_optional(req, db=db_session)
    assert user is not None
    assert user.id == test_user.id
    assert user.username == "testadmin"

    # Enforce current user
    enforced = get_current_user(req, db=db_session)
    assert enforced.id == test_user.id


def test_get_current_user_unauthenticated_redirect(db_session):
    req = MagicMock(spec=Request)
    req.cookies = {}
    req.headers = {"accept": "text/html"}
    req.method = "GET"

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(req, db=db_session)
    assert exc_info.value.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert exc_info.value.headers["Location"] == "/login"


def test_login_action_success_and_cookie(test_user, db_session):
    req = MagicMock(spec=Request)
    response = login_action(
        request=req,
        username="testadmin",
        password="adminpass123",
        db=db_session
    )
    assert isinstance(response, RedirectResponse)
    assert response.status_code == status.HTTP_303_SEE_OTHER
    assert response.headers["location"] == "/"

    # Cookie check
    set_cookie_header = response.headers.get("set-cookie")
    assert set_cookie_header is not None
    assert SESSION_COOKIE_NAME in set_cookie_header


def test_login_action_invalid_password(test_user, db_session):
    req = MagicMock(spec=Request)
    response = login_action(
        request=req,
        username="testadmin",
        password="wrongpassword",
        db=db_session
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid username or password" in response.body.decode()


def test_logout_action():
    response = logout_action()
    assert isinstance(response, RedirectResponse)
    assert response.status_code == status.HTTP_303_SEE_OTHER
    assert response.headers["location"] == "/login"
    assert SESSION_COOKIE_NAME in response.headers.get("set-cookie", "")


def test_user_management_lifecycle(test_user, db_session):
    req = MagicMock(spec=Request)

    # 1. List users
    list_resp = users_management_page(request=req, current_user=test_user, db=db_session)
    assert list_resp.status_code == 200
    assert len(list_resp.context["users"]) == 1

    # 2. Create second user
    create_resp = create_user_action(
        request=req,
        username="operator1",
        password="password123",
        email="operator1@reccalab.com",
        is_admin=False,
        current_user=test_user,
        db=db_session
    )
    assert create_resp.status_code == status.HTTP_303_SEE_OTHER

    new_user = db_session.query(User).filter(User.username == "operator1").first()
    assert new_user is not None
    assert new_user.is_admin is False
    assert new_user.is_active is True

    # 3. Toggle user active status
    toggle_user_active(user_id=new_user.id, current_user=test_user, db=db_session)
    db_session.refresh(new_user)
    assert new_user.is_active is False

    # 4. Cannot deactivate self
    with pytest.raises(HTTPException) as exc_info:
        toggle_user_active(user_id=test_user.id, current_user=test_user, db=db_session)
    assert exc_info.value.status_code == 400

    # 5. Delete second user
    del_resp = delete_user_action(user_id=new_user.id, current_user=test_user, db=db_session)
    assert del_resp.status_code == 200
    assert db_session.query(User).filter(User.id == new_user.id).first() is None

    # 6. Cannot delete self
    with pytest.raises(HTTPException) as exc_info:
        delete_user_action(user_id=test_user.id, current_user=test_user, db=db_session)
    assert exc_info.value.status_code == 400

