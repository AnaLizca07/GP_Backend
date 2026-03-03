import pytest
from pydantic import ValidationError
from datetime import datetime

from app.schemas.user import (
    UserBase,
    UserCreate,
    UserLogin,
    User,
    Token,
    TokenData,
)


def test_userbase_ok():
    u = UserBase(email="test@example.com", role="manager")
    assert u.email == "test@example.com"
    assert u.role == "manager"


def test_userbase_invalid_email():
    with pytest.raises(ValidationError):
        UserBase(email="no-es-email", role="manager")


def test_userbase_missing_role():
    with pytest.raises(ValidationError):
        UserBase(email="test@example.com")  # type: ignore


def test_usercreate_ok():
    u = UserCreate(email="test@example.com", role="employee", password="123456")
    assert u.password == "123456"
    assert u.role == "employee"


def test_usercreate_missing_password():
    with pytest.raises(ValidationError):
        UserCreate(email="test@example.com", role="employee")  # type: ignore


def test_userlogin_ok():
    login = UserLogin(email="test@example.com", password="123456")
    assert login.email == "test@example.com"


def test_userlogin_missing_password():
    with pytest.raises(ValidationError):
        UserLogin(email="test@example.com")  # type: ignore


def test_user_ok():
    now = datetime.utcnow()
    user = User(id="abc123", email="test@example.com", role="sponsor", created_at=now)
    assert user.id == "abc123"
    assert user.created_at == now


def test_token_default_type():
    now = datetime.utcnow()
    user = User(id="abc123", email="test@example.com", role="manager", created_at=now)
    token = Token(access_token="token123", user=user)
    assert token.access_token == "token123"
    assert token.token_type == "bearer"  # default


def test_tokendata_ok_optional_fields():
    data = TokenData()
    assert data.email is None
    assert data.role is None


def test_tokendata_ok_with_values():
    data = TokenData(email="test@example.com", role="manager")
    assert data.email == "test@example.com"
    assert data.role == "manager"