import pytest
from pydantic import ValidationError

from app.models.auth import UserRegister, UserLogin, TokenPayload, UserRole


def test_user_role_enum_values():
    assert UserRole.MANAGER.value == "manager"
    assert UserRole.EMPLOYEE.value == "employee"
    assert UserRole.SPONSOR.value == "sponsor"


def test_user_register_ok():
    u = UserRegister(email="test@example.com", password="123456", role=UserRole.MANAGER)
    assert u.email == "test@example.com"
    assert u.role == UserRole.MANAGER


def test_user_register_password_too_short():
    with pytest.raises(ValidationError):
        UserRegister(email="test@example.com", password="123", role=UserRole.EMPLOYEE)


def test_user_register_invalid_email():
    with pytest.raises(ValidationError):
        UserRegister(email="no-es-email", password="123456", role=UserRole.SPONSOR)


def test_user_register_invalid_role_value_string():
    # Si tu modelo acepta role como Enum, esto debe fallar (o ajusta según tu implementación)
    with pytest.raises(Exception):
        UserRegister(email="test@example.com", password="123456", role="admin")  # type: ignore


def test_user_login_ok():
    login = UserLogin(email="test@example.com", password="123456")
    assert login.email == "test@example.com"


def test_user_login_missing_password():
    with pytest.raises(ValidationError):
        UserLogin(email="test@example.com")  # type: ignore


def test_token_payload_ok():
    t = TokenPayload(sub="user-id", email="test@example.com", role="manager")
    assert t.sub == "user-id"
    assert t.role == "manager"